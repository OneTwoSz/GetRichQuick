"""
Allocation engine — pure, deterministic, no I/O.

Splits ProductionBatch consumption across the orders the batch served,
following the ISO 14044 hierarchy (subdivision > physical/mass > units >
economic) and recording which rung was used. Everything here operates on
plain dataclasses so it can be unit-tested without a database; the routes
layer maps ORM rows in and out.

Invariants the acceptance tests pin down:
  - Order shares + leftover share sum to exactly 1.0.
  - Unallocated fabric carries its pro-rata footprint to FabricInventory;
    orders are charged at batch intensity for their own kg only — leftover
    is never spread back onto them, and nothing vanishes.
  - Rework inputs are added to the ORIGINAL batch's orders pro rata.
  - Facility overhead (monthly total − Σ batch-attributed) spreads across
    the month's output by mass.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..models import AllocationMethod, DataQuality

# Tolerance for float comparisons on kg quantities.
_EPS = 1e-9


@dataclass(frozen=True)
class AllocationLine:
    """One order's claim on a batch, before shares are computed."""
    order_id: int
    fabric_kg: float
    garment_units: Optional[int] = None
    order_value: Optional[float] = None


@dataclass(frozen=True)
class AllocationResult:
    method: AllocationMethod
    # order_id -> share of the whole batch (0..1)
    shares: Dict[int, float]
    # share of the batch not claimed by any order (buffer / leftover fabric)
    leftover_share: float
    leftover_fabric_kg: float


def fabric_demand_kg(units: int, net_garment_weight_kg: float, cutting_waste_percent: float) -> float:
    """Fabric an order needs, including its style's cutting waste.

    units × net weight ÷ (1 − waste%). A style that wastes more fabric at
    the cutting table correctly demands (and is charged for) more of the
    batch. E.g. 1,000 units × 0.2 kg at 20% waste → 250 kg.
    """
    if not 0 <= cutting_waste_percent < 100:
        raise ValueError("cutting_waste_percent must be in [0, 100)")
    return units * net_garment_weight_kg / (1 - cutting_waste_percent / 100)


def compute_shares(
    total_fabric_kg: float,
    lines: List[AllocationLine],
    method: AllocationMethod = AllocationMethod.MASS,
) -> AllocationResult:
    """Split a batch across orders per the ISO 14044 rung chosen.

    The fraction of the batch claimed by orders is always mass-based
    (Σ fabric_kg ÷ total): fabric that no order claims is leftover and
    keeps its pro-rata footprint. The claimed fraction is then divided
    among orders by the method's metric — for MASS this reduces to each
    order's fabric_kg ÷ total; UNITS uses garment counts (only sensible
    when garments are near-identical in weight); ECONOMIC uses order value
    (fallback only — reports flag it).
    """
    if total_fabric_kg <= 0:
        raise ValueError("total_fabric_kg must be positive")
    if not lines:
        return AllocationResult(method, {}, 1.0, total_fabric_kg)

    claimed_kg = sum(l.fabric_kg for l in lines)
    if any(l.fabric_kg < 0 for l in lines):
        raise ValueError("fabric_kg cannot be negative")
    if claimed_kg > total_fabric_kg + _EPS:
        raise ValueError(
            f"orders claim {claimed_kg} kg but batch only processed {total_fabric_kg} kg"
        )
    order_ids = [l.order_id for l in lines]
    if len(set(order_ids)) != len(order_ids):
        raise ValueError("duplicate order in allocation lines")

    claimed_fraction = min(claimed_kg / total_fabric_kg, 1.0)

    # Subdivision: a batch that genuinely served one order needs no
    # allocation — its share is the whole claimed fraction.
    if len(lines) == 1:
        weights = {lines[0].order_id: 1.0}
    elif method == AllocationMethod.MASS:
        weights = {l.order_id: l.fabric_kg / claimed_kg for l in lines}
    elif method == AllocationMethod.UNITS:
        if any(l.garment_units is None or l.garment_units <= 0 for l in lines):
            raise ValueError("UNITS allocation requires garment_units on every line")
        total_units = sum(l.garment_units for l in lines)
        weights = {l.order_id: l.garment_units / total_units for l in lines}
    elif method == AllocationMethod.ECONOMIC:
        if any(l.order_value is None or l.order_value <= 0 for l in lines):
            raise ValueError("ECONOMIC allocation requires order_value on every line")
        total_value = sum(l.order_value for l in lines)
        weights = {l.order_id: l.order_value / total_value for l in lines}
    else:  # pragma: no cover - enum is exhaustive
        raise ValueError(f"unknown allocation method {method}")

    shares = {oid: w * claimed_fraction for oid, w in weights.items()}

    # Float residual correction so shares + leftover sum to EXACTLY 1.0
    # (auditors add the column up). Dump the residual on the largest share
    # where it is relatively smallest.
    leftover_share = 1.0 - claimed_fraction
    residual = 1.0 - (sum(shares.values()) + leftover_share)
    if residual != 0.0:
        largest = max(shares, key=lambda oid: shares[oid])
        shares[largest] += residual

    return AllocationResult(
        method=method,
        shares=shares,
        leftover_share=leftover_share,
        leftover_fabric_kg=total_fabric_kg - claimed_kg,
    )


def allocate_quantity(quantity: float, result: AllocationResult) -> Dict[int, float]:
    """Split one batch input quantity across orders by their shares.

    The leftover share's portion is NOT in the returned dict — it belongs
    to FabricInventory (see leftover_quantity)."""
    return {oid: quantity * share for oid, share in result.shares.items()}


def leftover_quantity(quantity: float, result: AllocationResult) -> float:
    """The slice of a batch input carried by unclaimed (leftover) fabric."""
    return quantity * result.leftover_share


def rework_allocation(original: AllocationResult) -> AllocationResult:
    """Shares for a rework (re-dye / re-process) batch.

    A rework run is a new batch, but its consumption honestly belongs to
    the original batch's orders — added pro rata to their existing shares.
    Leftover fabric of the original keeps carrying its slice too."""
    return AllocationResult(
        method=original.method,
        shares=dict(original.shares),
        leftover_share=original.leftover_share,
        leftover_fabric_kg=original.leftover_fabric_kg,
    )


@dataclass(frozen=True)
class MassPoint:
    """Anything that receives an overhead spread: an order allocation (or a
    whole batch) identified by key, weighted by its fabric mass."""
    key: int
    fabric_kg: float


def spread_overhead(
    monthly_total: float,
    attributed_total: float,
    points: List[MassPoint],
) -> Dict[int, float]:
    """The single-meter problem: whatever the monthly bill shows beyond the
    sum of batch-attributed inputs is facility overhead, spread across the
    month's output by mass. 12,000 kWh with 9,000 attributed → 3,000 spread.

    A negative overhead (bills below attributed inputs — usually a data
    entry error) is clamped to zero rather than crediting orders."""
    overhead = max(monthly_total - attributed_total, 0.0)
    total_mass = sum(p.fabric_kg for p in points)
    if overhead == 0.0 or total_mass <= 0:
        return {p.key: 0.0 for p in points}
    return {p.key: overhead * p.fabric_kg / total_mass for p in points}


@dataclass(frozen=True)
class QualityContribution:
    """One input's contribution to a footprint, tagged with its tier."""
    amount: float  # any consistent unit — kg CO2e, or raw quantity
    quality: DataQuality


def data_quality_mix(contributions: List[QualityContribution]) -> Dict[str, float]:
    """Percentage of a footprint from MEASURED / ESTIMATED / DEFAULT_FACTOR
    inputs. This is the mix buyers' auditors ask for; reports and DPPs
    print it per order."""
    mix = {q.value: 0.0 for q in DataQuality}
    total = sum(c.amount for c in contributions)
    if total <= 0:
        return mix
    for c in contributions:
        mix[c.quality.value] += c.amount
    return {k: round(v / total * 100, 2) for k, v in mix.items()}
