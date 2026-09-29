"""
Assembles life-cycle engine inputs from the database (Phase 3).

This is where GreenThread's factory-side data becomes the primary-data
backbone of a product footprint:

  - Factory primary: every order of the product that has batch
    allocations contributes its allocated batch inputs (plus reworks,
    facility overhead and consumed leftover stock), grouped by the
    process → life-cycle stage map below and divided by the units of the
    orders that went through that stage. That is the same allocation the
    Phase 2 order footprint uses, just broken out by stage.
  - Supplier primary: the latest submission from the supplier linked to a
    stage, turned into per-kg intensities.
  - Supplier declared: BOM carbon_factor_override values.
  - Everything else falls through to the factor library, and says so.
"""
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import (
    BatchInputType,
    DataQuality,
    FabricInventory,
    InventoryStatus,
    MaterialCategory,
    Order,
    ProcessType,
    Product,
    ProductLifecycle,
    ProductSupplier,
    ProductionBatch,
    SupplierSubmission,
)
from ..utils import factor_library as fl
from . import lifecycle
from .batch_carbon import batch_totals, effective_inputs, monthly_reconciliation
from ..utils.constants import BATCH_INPUT_EMISSION_FACTORS

PROCESS_STAGE = {
    ProcessType.KNITTING: "fabric_production",
    ProcessType.BLEACHING: "wet_processing",
    ProcessType.DYEING: "wet_processing",
    ProcessType.PRINTING: "wet_processing",
    ProcessType.FINISHING: "wet_processing",
    ProcessType.CUTTING_SEWING: "assembly",
}

SUBMISSION_INPUTS = ("electricity_kwh", "water_l", "steam_kg", "diesel_l", "chemical_kg", "dye_kg")


def lifecycle_settings(db: Session, product: Product) -> ProductLifecycle:
    """The product's saved settings, or an unsaved default row."""
    row = db.query(ProductLifecycle).filter(ProductLifecycle.product_id == product.id).first()
    return row or ProductLifecycle(
        product_id=product.id, boundary="cradle_to_gate", packaging=[], distribution=[],
        washes=0, tumble_dry=False, use_country="EU", end_of_life="eu_average",
    )


@dataclass
class _StageTotals:
    co2e: float = 0.0
    water: float = 0.0
    kwh: float = 0.0
    quality: Dict[DataQuality, float] = field(default_factory=dict)
    order_ids: set = field(default_factory=set)
    batch_ids: set = field(default_factory=set)

    def add(self, co2e: float, quality: DataQuality, water: float = 0.0, kwh: float = 0.0):
        self.co2e += co2e
        self.water += water
        self.kwh += kwh
        self.quality[quality] = self.quality.get(quality, 0.0) + co2e


def _batch_kwh(batch: ProductionBatch) -> float:
    return sum(i.quantity for i in effective_inputs(batch)
               if i.input_type == BatchInputType.ELECTRICITY_KWH.value)


def factory_primary_by_stage(db: Session, product: Product) -> Dict[str, lifecycle.StageActivity]:
    """Per-garment factory data for each stage the product's orders
    actually went through."""
    orders = db.query(Order).filter(Order.product_id == product.id).all()
    totals: Dict[str, _StageTotals] = {}
    units_by_order = {o.id: o.units for o in orders}
    recon_cache: Dict[Tuple[int, int, int], Optional[Dict]] = {}

    for order in orders:
        for alloc in order.allocations:
            batch = alloc.batch
            stage = PROCESS_STAGE[batch.process_type]
            t = totals.setdefault(stage, _StageTotals())
            t.order_ids.add(order.id)
            share = alloc.allocated_share
            for b in [batch, *batch.reworks]:
                t.batch_ids.add(b.id)
                bt = batch_totals(b)
                for c in bt.contributions:
                    t.add(c.amount * share, c.quality)
                t.water += bt.water_l * share
                t.kwh += _batch_kwh(b) * share

            # Facility overhead from the monthly utility reconciliation,
            # charged to the stage of the batch it was spread onto.
            if not batch.outsourced:
                key = (batch.factory_id, batch.started_at.year, batch.started_at.month)
                if key not in recon_cache:
                    recon_cache[key] = monthly_reconciliation(db, *key)
                recon = recon_cache[key]
                per_batch = (recon or {}).get("per_batch", {}).get(batch.id)
                if per_batch:
                    kwh = per_batch["overhead_kwh"] * share
                    water = per_batch["overhead_water_l"] * share
                    co2e = (kwh * BATCH_INPUT_EMISSION_FACTORS["electricity_kwh"]
                            + water * BATCH_INPUT_EMISSION_FACTORS["water_l"])
                    t.add(co2e, DataQuality.ESTIMATED, water=water, kwh=kwh)

        # Leftover stock consumed by this order carries its source batch's
        # embodied footprint into that batch's stage.
        consumed = db.query(FabricInventory).filter(
            FabricInventory.consumed_by_order_id == order.id,
            FabricInventory.status == InventoryStatus.CONSUMED,
        ).all()
        for item in consumed:
            stage = PROCESS_STAGE[item.source_batch.process_type]
            t = totals.setdefault(stage, _StageTotals())
            t.order_ids.add(order.id)
            t.add(item.embodied_co2_kg, DataQuality.ESTIMATED, water=item.embodied_water_l)

    result = {}
    for stage, t in totals.items():
        units = sum(units_by_order[o] for o in t.order_ids)
        if units <= 0:
            continue
        result[stage] = lifecycle.StageActivity(
            co2e_kg=t.co2e / units,
            water_l=t.water / units,
            energy_kwh=t.kwh / units,
            quality_amounts={q: v / units for q, v in t.quality.items()},
            source=(f"allocated batch data: {len(t.batch_ids)} batch(es), "
                    f"{len(t.order_ids)} order(s), {units:,} units"),
        )
    return result


def _links(db: Session, product: Product) -> List[ProductSupplier]:
    return db.query(ProductSupplier).filter(ProductSupplier.product_id == product.id).all()


def latest_submission(db: Session, supplier_id: int, stage) -> Optional[SupplierSubmission]:
    return (
        db.query(SupplierSubmission)
        .filter(SupplierSubmission.supplier_id == supplier_id,
                SupplierSubmission.stage == stage,
                SupplierSubmission.output_kg > 0)
        .order_by(SupplierSubmission.created_at.desc(), SupplierSubmission.id.desc())
        .first()
    )


def submission_intensity(sub: SupplierSubmission) -> Dict[str, float]:
    return {k: getattr(sub, k) / sub.output_kg for k in SUBMISSION_INPUTS if getattr(sub, k)}


def build_inputs(db: Session, product: Product, boundary: Optional[str] = None) -> lifecycle.LifecycleInputs:
    settings = lifecycle_settings(db, product)

    fibres, trims = [], []
    for item in product.bom_items:
        if item.category == MaterialCategory.FIBER:
            fibres.append(lifecycle.FibreLine(item.material_key, item.quantity_per_garment_g,
                                              item.carbon_factor_override))
        elif item.category == MaterialCategory.TRIM:
            trims.append(lifecycle.MaterialLine(item.material_key, item.quantity_per_garment_g,
                                                item.carbon_factor_override))
        # DYE / CHEMICAL lines: charged by wet processing (see lifecycle docstring).

    stage_countries: Dict[str, str] = {}
    intensities: Dict[str, lifecycle.SupplierIntensity] = {}
    for link in _links(db, product):
        stage = link.stage.value
        stage_countries[stage] = link.supplier.country
        if stage in lifecycle.MANUFACTURING_STAGES:
            sub = latest_submission(db, link.supplier_id, link.stage)
            if sub:
                intensities[stage] = lifecycle.SupplierIntensity(
                    inputs_per_kg=submission_intensity(sub),
                    quality=sub.data_quality,
                    source=(f"supplier submission: {link.supplier.name}"
                            + (f", {sub.period_label}" if sub.period_label else "")),
                    country=link.supplier.country,
                )

    return lifecycle.LifecycleInputs(
        garment_weight_g=product.garment_weight_g,
        cutting_waste_percent=product.cutting_waste_percent or 0.0,
        fibres=fibres,
        trims=trims,
        packaging=[lifecycle.MaterialLine(p.get("material_key"), float(p.get("grams", 0)))
                   for p in (settings.packaging or [])],
        factory_country=fl.DEFAULT_COUNTRY,
        stage_countries=stage_countries,
        factory_primary=factory_primary_by_stage(db, product),
        supplier_intensities=intensities,
        distribution=[lifecycle.TransportLeg(d.get("mode"), float(d.get("distance_km", 0)))
                      for d in (settings.distribution or [])],
        boundary=boundary or settings.boundary,
        washes=settings.washes,
        tumble_dry=settings.tumble_dry,
        use_country=settings.use_country,
        end_of_life=settings.end_of_life,
    )


def product_footprint(db: Session, product: Product, boundary: Optional[str] = None) -> lifecycle.LifecycleResult:
    return lifecycle.compute(build_inputs(db, product, boundary))


def apply_scenario(inputs: lifecycle.LifecycleInputs, scenario) -> lifecycle.LifecycleInputs:
    """What-if variant of a product's inputs (ecodesign comparisons).

    `scenario` is a ScenarioRequest: fibre swaps replace a material_key
    (dropping any supplier-declared factor, which belonged to the old
    material); stage_countries move a stage to another country (and drop
    that stage's primary data, which was measured somewhere else)."""
    out = replace(inputs)
    if scenario.fibre_swaps:
        out.fibres = [
            lifecycle.FibreLine(scenario.fibre_swaps[f.material_key], f.net_g, None)
            if f.material_key in scenario.fibre_swaps else f
            for f in inputs.fibres
        ]
    if scenario.stage_countries:
        out.stage_countries = {**inputs.stage_countries, **scenario.stage_countries}
        out.factory_primary = {s: a for s, a in inputs.factory_primary.items()
                               if s not in scenario.stage_countries}
        out.supplier_intensities = {s: a for s, a in inputs.supplier_intensities.items()
                                    if s not in scenario.stage_countries}
    if scenario.distribution is not None:
        out.distribution = [lifecycle.TransportLeg(l.mode, l.distance_km) for l in scenario.distribution]
    if scenario.boundary:
        out.boundary = scenario.boundary
    if scenario.washes is not None:
        out.washes = scenario.washes
    if scenario.end_of_life:
        out.end_of_life = scenario.end_of_life
    return out
