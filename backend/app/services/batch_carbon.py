"""
Batch-level carbon accounting — the phase-2 replacement for per-order
inputs. The existing CarbonCalculator (per ProductionRecord) remains as
"simple mode" for single-order batches and legacy data; this module handles
the batch → allocation → order path.

Responsibilities:
  - Turn a batch's inputs into CO2/water totals, synthesizing DEFAULT_FACTOR
    inputs when a batch (typically an outsourced dye lot) has none.
  - Reconstruct the engine's AllocationResult from stored BatchAllocation
    rows (shares are persisted for audit immutability).
  - Compute an order's footprint: its share of every batch that touched it,
    plus rework batches pro rata, plus embodied footprint transferred from
    consumed FabricInventory, plus its slice of monthly facility overhead.
  - Produce the Allocation Statement and data-quality mix that reports and
    the buyer share link print.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import (
    AllocationMethod,
    BatchInput,
    BatchInputType,
    DataQuality,
    FabricInventory,
    InventoryStatus,
    MonthlyUtility,
    Order,
    ProductionBatch,
)
from ..utils.constants import (
    BATCH_INPUT_EMISSION_FACTORS,
    PROCESS_DEFAULT_INPUT_FACTORS,
)
from .allocation import (
    AllocationResult,
    QualityContribution,
    data_quality_mix,
)


@dataclass
class EffectiveInput:
    """A batch input after default-factor synthesis: what we actually
    charge the batch for, with its data-quality tier."""
    input_type: str  # BatchInputType value
    quantity: float
    quality: DataQuality
    source: Optional[str] = None


@dataclass
class BatchTotals:
    co2_kg: float
    water_l: float
    contributions: List[QualityContribution] = field(default_factory=list)
    used_default_factors: bool = False


@dataclass
class BatchLine:
    """One row of an order's Allocation Statement."""
    batch_id: int
    batch_code: str
    process_type: str
    allocation_method: str
    allocated_share: float
    co2_kg: float
    water_l: float
    is_rework: bool
    outsourced: bool
    data_quality_flags: List[str] = field(default_factory=list)
    allocation_note: Optional[str] = None


@dataclass
class OrderFootprint:
    order_id: int
    co2_kg: float
    water_l: float
    batch_lines: List[BatchLine]
    embodied_co2_kg: float   # transferred in from consumed FabricInventory
    embodied_water_l: float
    overhead_co2_kg: float   # slice of monthly facility overhead
    overhead_water_l: float
    quality_mix: Dict[str, float]  # % of CO2 by MEASURED/ESTIMATED/DEFAULT_FACTOR
    used_economic_allocation: bool


def effective_inputs(batch: ProductionBatch) -> List[EffectiveInput]:
    """The inputs a batch is charged for.

    A batch with logged inputs uses them as-is. A batch with none — the
    day-one reality for outsourced dyeing — falls back to built-in
    per-process defaults scaled by fabric kg, tagged DEFAULT_FACTOR."""
    if batch.inputs:
        return [
            EffectiveInput(
                input_type=i.input_type.value,
                quantity=i.quantity,
                quality=i.data_quality,
                source=i.source,
            )
            for i in batch.inputs
        ]
    defaults = PROCESS_DEFAULT_INPUT_FACTORS.get(batch.process_type.value, {})
    return [
        EffectiveInput(
            input_type=input_type,
            quantity=per_kg * batch.total_fabric_kg,
            quality=DataQuality.DEFAULT_FACTOR,
            source=f"built-in default for {batch.process_type.value}",
        )
        for input_type, per_kg in defaults.items()
    ]


def batch_totals(batch: ProductionBatch) -> BatchTotals:
    """CO2 and water totals for one batch, with per-tier contributions."""
    co2 = 0.0
    water = 0.0
    contributions: List[QualityContribution] = []
    used_defaults = False
    for inp in effective_inputs(batch):
        factor = BATCH_INPUT_EMISSION_FACTORS.get(inp.input_type, 0.0)
        input_co2 = inp.quantity * factor
        co2 += input_co2
        contributions.append(QualityContribution(amount=input_co2, quality=inp.quality))
        if inp.input_type == BatchInputType.WATER_L.value:
            water += inp.quantity
        if inp.quality == DataQuality.DEFAULT_FACTOR:
            used_defaults = True
    return BatchTotals(co2_kg=co2, water_l=water, contributions=contributions,
                       used_default_factors=used_defaults)


def stored_allocation_result(batch: ProductionBatch) -> AllocationResult:
    """Rebuild the engine result from persisted shares. Shares are stored at
    allocation time so reports stay reproducible even if the batch is later
    edited — we trust the rows, not a recomputation."""
    shares = {a.order_id: a.allocated_share for a in batch.allocations}
    claimed = sum(a.fabric_kg for a in batch.allocations)
    return AllocationResult(
        method=batch.allocation_method,
        shares=shares,
        leftover_share=max(0.0, 1.0 - sum(shares.values())),
        leftover_fabric_kg=max(0.0, batch.total_fabric_kg - claimed),
    )


def _month_key(batch: ProductionBatch) -> Tuple[int, int]:
    return batch.started_at.year, batch.started_at.month


def monthly_reconciliation(
    db: Session, factory_id: int, year: int, month: int
) -> Optional[Dict]:
    """§4 single-meter reconciliation for one month.

    overhead = monthly bill totals − Σ batch-attributed inputs, spread by
    mass across the month's in-house batches. Outsourced batches are
    excluded on both sides — their consumption never hit this meter.
    Returns None when no MonthlyUtility entry exists for the month."""
    entry = (
        db.query(MonthlyUtility)
        .filter(
            MonthlyUtility.factory_id == factory_id,
            MonthlyUtility.year == year,
            MonthlyUtility.month == month,
        )
        .first()
    )
    if entry is None:
        return None

    batches = [
        b
        for b in db.query(ProductionBatch)
        .filter(ProductionBatch.factory_id == factory_id, ProductionBatch.outsourced == False)  # noqa: E712
        .all()
        if _month_key(b) == (year, month)
    ]

    attributed_kwh = 0.0
    attributed_water = 0.0
    for b in batches:
        for i in b.inputs:
            if i.input_type == BatchInputType.ELECTRICITY_KWH:
                attributed_kwh += i.quantity
            elif i.input_type == BatchInputType.WATER_L:
                attributed_water += i.quantity

    overhead_kwh = max(entry.total_electricity_kwh - attributed_kwh, 0.0)
    overhead_water = max(entry.total_water_liters - attributed_water, 0.0)
    total_mass = sum(b.total_fabric_kg for b in batches)

    per_batch = {}
    for b in batches:
        weight = (b.total_fabric_kg / total_mass) if total_mass > 0 else 0.0
        per_batch[b.id] = {
            "batch_code": b.batch_code,
            "fabric_kg": b.total_fabric_kg,
            "overhead_kwh": overhead_kwh * weight,
            "overhead_water_l": overhead_water * weight,
        }

    return {
        "year": year,
        "month": month,
        "total_electricity_kwh": entry.total_electricity_kwh,
        "total_water_liters": entry.total_water_liters,
        "attributed_kwh": attributed_kwh,
        "attributed_water_l": attributed_water,
        "overhead_kwh": overhead_kwh,
        "overhead_water_l": overhead_water,
        "total_fabric_kg": total_mass,
        "per_batch": per_batch,
    }


def _order_overhead(db: Session, order: Order) -> Tuple[float, float, float]:
    """The order's slice of facility overhead: for each in-house batch that
    served it, the batch's overhead × the order's stored share.

    Returns (co2_kg, water_l, kwh). Zero when no MonthlyUtility entry
    exists for a batch's month — reconciliation is opt-in per month."""
    co2 = 0.0
    water = 0.0
    kwh = 0.0
    recon_cache: Dict[Tuple[int, int], Optional[Dict]] = {}
    for alloc in order.allocations:
        batch = alloc.batch
        if batch.outsourced:
            continue
        key = _month_key(batch)
        if key not in recon_cache:
            recon_cache[key] = monthly_reconciliation(db, batch.factory_id, *key)
        recon = recon_cache[key]
        if not recon:
            continue
        batch_overhead = recon["per_batch"].get(batch.id)
        if not batch_overhead:
            continue
        order_kwh = batch_overhead["overhead_kwh"] * alloc.allocated_share
        order_water = batch_overhead["overhead_water_l"] * alloc.allocated_share
        kwh += order_kwh
        water += order_water
        co2 += (
            order_kwh * BATCH_INPUT_EMISSION_FACTORS["electricity_kwh"]
            + order_water * BATCH_INPUT_EMISSION_FACTORS["water_l"]
        )
    return co2, water, kwh


def order_footprint(db: Session, order: Order) -> OrderFootprint:
    """The full bottom-up footprint for one order."""
    co2 = 0.0
    water = 0.0
    lines: List[BatchLine] = []
    contributions: List[QualityContribution] = []
    used_economic = False

    for alloc in order.allocations:
        batch = alloc.batch
        share = alloc.allocated_share
        totals = batch_totals(batch)

        # Rework runs are separate batches but their consumption honestly
        # belongs to the original batch's orders, added pro rata at the
        # SAME share this order held in the original.
        batch_and_reworks = [(batch, totals)] + [
            (rb, batch_totals(rb)) for rb in batch.reworks
        ]

        for b, t in batch_and_reworks:
            line_co2 = t.co2_kg * share
            line_water = t.water_l * share
            co2 += line_co2
            water += line_water
            contributions.extend(
                QualityContribution(amount=c.amount * share, quality=c.quality)
                for c in t.contributions
            )
            flags = []
            if t.used_default_factors:
                flags.append("default_factors")
            if b.allocation_method == AllocationMethod.ECONOMIC:
                used_economic = True
                flags.append("economic_allocation")
            lines.append(BatchLine(
                batch_id=b.id,
                batch_code=b.batch_code,
                process_type=b.process_type.value,
                allocation_method=b.allocation_method.value,
                allocated_share=round(share, 6),
                co2_kg=round(line_co2, 4),
                water_l=round(line_water, 2),
                is_rework=b.is_rework,
                outsourced=b.outsourced,
                data_quality_flags=flags,
                allocation_note=b.allocation_note,
            ))

    # Leftover fabric consumed from stock: its embodied footprint transfers
    # to this order — no double counting, nothing vanishes.
    embodied_co2 = 0.0
    embodied_water = 0.0
    consumed = (
        db.query(FabricInventory)
        .filter(
            FabricInventory.consumed_by_order_id == order.id,
            FabricInventory.status == InventoryStatus.CONSUMED,
        )
        .all()
    )
    for item in consumed:
        embodied_co2 += item.embodied_co2_kg
        embodied_water += item.embodied_water_l
        # Embodied stock keeps the quality of its source batch only in
        # aggregate; we book it as ESTIMATED — it is real primary data but
        # carried forward, not metered against this order.
        contributions.append(
            QualityContribution(amount=item.embodied_co2_kg, quality=DataQuality.ESTIMATED)
        )

    overhead_co2, overhead_water, _ = _order_overhead(db, order)
    if overhead_co2 > 0:
        # Overhead derives from the utility bill: ESTIMATED tier.
        contributions.append(
            QualityContribution(amount=overhead_co2, quality=DataQuality.ESTIMATED)
        )

    return OrderFootprint(
        order_id=order.id,
        co2_kg=round(co2 + embodied_co2 + overhead_co2, 4),
        water_l=round(water + embodied_water + overhead_water, 2),
        batch_lines=lines,
        embodied_co2_kg=round(embodied_co2, 4),
        embodied_water_l=round(embodied_water, 2),
        overhead_co2_kg=round(overhead_co2, 4),
        overhead_water_l=round(overhead_water, 2),
        quality_mix=data_quality_mix(contributions),
        used_economic_allocation=used_economic,
    )


def rework_rate(db: Session, factory_id: int) -> float:
    """Rework batches ÷ total batches. A cost AND an emissions problem —
    surfacing it gives the factory a number it can improve."""
    total = (
        db.query(ProductionBatch)
        .filter(ProductionBatch.factory_id == factory_id)
        .count()
    )
    if total == 0:
        return 0.0
    reworks = (
        db.query(ProductionBatch)
        .filter(
            ProductionBatch.factory_id == factory_id,
            ProductionBatch.is_rework == True,  # noqa: E712
        )
        .count()
    )
    return round(reworks / total, 4)
