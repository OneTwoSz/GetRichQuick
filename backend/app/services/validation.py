"""
Automated data checks — the first verification gate (Phase 3).

Runs before a passport can be published and on demand from the product
page. Three severities:

  error    blocks publishing — the data is physically implausible or
           internally contradictory (e.g. more fibre than garment)
  warning  publishable, but a reviewer should look (outlier intensity,
           duplicate entry, missing scenario data)
  info     coverage gaps worth closing (orders with no batch data)

Plausibility ranges are deliberately wide: they catch unit mistakes
(litres typed as kilolitres, Wh as kWh) rather than second-guessing a
well-run mill. An intensity outside the WARN range is a warning; one more
than 10× outside it is an error.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import MaterialCategory, Order, Product, ProductSupplier
from ..utils import factor_library as fl
from . import lifecycle
from .batch_carbon import monthly_reconciliation
from .product_footprint import (
    PROCESS_STAGE,
    factory_primary_by_stage,
    latest_submission,
    lifecycle_settings,
    submission_intensity,
)

# (low, high) per kg of the stage's output, by stage and input type.
PLAUSIBLE_INTENSITY: Dict[str, Dict[str, Tuple[float, float]]] = {
    "yarn_production": {"electricity_kwh": (1.0, 10.0), "water_l": (0.0, 20.0)},
    "fabric_production": {"electricity_kwh": (0.1, 4.0), "water_l": (0.0, 10.0)},
    "wet_processing": {
        "electricity_kwh": (0.1, 6.0), "water_l": (10.0, 350.0),
        "steam_kg": (0.0, 15.0), "chemical_kg": (0.0, 2.0), "dye_kg": (0.0, 0.2),
    },
    "assembly": {"electricity_kwh": (0.05, 3.0), "water_l": (0.0, 10.0)},
}
HARD_LIMIT_MULTIPLE = 10.0


@dataclass
class Issue:
    severity: str   # error | warning | info
    code: str
    message: str
    entity: Optional[str] = None


def _check_intensity(issues: List[Issue], stage: str, input_type: str, per_kg: float, where: str):
    band = PLAUSIBLE_INTENSITY.get(stage, {}).get(input_type)
    if band is None:
        return
    low, high = band
    if per_kg > high * HARD_LIMIT_MULTIPLE or (low > 0 and per_kg < low / HARD_LIMIT_MULTIPLE):
        issues.append(Issue("error", "intensity_implausible",
                            f"{where}: {input_type} of {per_kg:.3g}/kg is far outside "
                            f"{low}–{high}/kg for {stage} — check units", where))
    elif per_kg > high or per_kg < low:
        issues.append(Issue("warning", "intensity_outlier",
                            f"{where}: {input_type} of {per_kg:.3g}/kg is outside the "
                            f"typical {low}–{high}/kg for {stage}", where))


def validate_product(db: Session, product: Product) -> List[Issue]:
    issues: List[Issue] = []

    # --- Bill of materials -------------------------------------------------
    fibres = [i for i in product.bom_items if i.category == MaterialCategory.FIBER]
    if not fibres:
        issues.append(Issue("warning", "no_fibre_lines",
                            "No fibre lines in the BOM — raw materials use a generic fibre factor",
                            f"product:{product.sku}"))
    else:
        fibre_g = sum(i.quantity_per_garment_g for i in fibres)
        if fibre_g > product.garment_weight_g * 1.25:
            issues.append(Issue("error", "fibre_exceeds_garment",
                                f"BOM fibre ({fibre_g:.0f} g) exceeds garment weight "
                                f"({product.garment_weight_g:.0f} g) by more than 25%",
                                f"product:{product.sku}"))
        elif abs(fibre_g - product.garment_weight_g) > product.garment_weight_g * 0.15:
            issues.append(Issue("warning", "fibre_weight_mismatch",
                                f"BOM fibre ({fibre_g:.0f} g) differs from garment weight "
                                f"({product.garment_weight_g:.0f} g) by more than 15%",
                                f"product:{product.sku}"))
        for i in fibres:
            if (i.material_key or "") not in fl.FIBRE_FACTORS and i.carbon_factor_override is None:
                issues.append(Issue("warning", "unknown_fibre",
                                    f"Fibre '{i.material_name}' has no recognised material_key — "
                                    f"generic factor used", f"bom:{i.id}"))

    # --- Factory batches behind the product's orders ------------------------
    orders = db.query(Order).filter(Order.product_id == product.id).all()
    seen_batches = set()
    months = set()
    for order in orders:
        if not order.allocations:
            issues.append(Issue("info", "order_without_batches",
                                f"Order {order.order_code} has no batch allocations yet — "
                                f"it does not contribute factory primary data", f"order:{order.id}"))
        for alloc in order.allocations:
            for batch in [alloc.batch, *alloc.batch.reworks]:
                if batch.id in seen_batches:
                    continue
                seen_batches.add(batch.id)
                if not batch.outsourced:
                    months.add((batch.factory_id, batch.started_at.year, batch.started_at.month))
                stage = PROCESS_STAGE[batch.process_type]
                sums: Dict[str, float] = {}
                seen_inputs = set()
                for inp in batch.inputs:
                    sums[inp.input_type.value] = sums.get(inp.input_type.value, 0.0) + inp.quantity
                    key = (inp.input_type, round(inp.quantity, 6), inp.source)
                    if key in seen_inputs:
                        issues.append(Issue("warning", "duplicate_input",
                                            f"Batch {batch.batch_code}: duplicate {inp.input_type.value} "
                                            f"entry of {inp.quantity:g}", f"batch:{batch.id}"))
                    seen_inputs.add(key)
                if batch.total_fabric_kg > 0:
                    for input_type, qty in sums.items():
                        _check_intensity(issues, stage, input_type, qty / batch.total_fabric_kg,
                                         f"Batch {batch.batch_code}")

    # --- Monthly utility reconciliation -------------------------------------
    for factory_id, year, month in sorted(months):
        recon = monthly_reconciliation(db, factory_id, year, month)
        if not recon:
            continue
        if recon["attributed_kwh"] > recon["total_electricity_kwh"] > 0:
            issues.append(Issue("warning", "attributed_exceeds_bill",
                                f"{year}-{month:02d}: batches record more electricity "
                                f"({recon['attributed_kwh']:.0f} kWh) than the bill "
                                f"({recon['total_electricity_kwh']:.0f} kWh)", f"utility:{year}-{month}"))
        if recon["attributed_water_l"] > recon["total_water_liters"] > 0:
            issues.append(Issue("warning", "attributed_exceeds_bill",
                                f"{year}-{month:02d}: batches record more water than the bill",
                                f"utility:{year}-{month}"))

    # --- Supplier submissions ----------------------------------------------
    links = db.query(ProductSupplier).filter(ProductSupplier.product_id == product.id).all()
    factory_stages = set(factory_primary_by_stage(db, product)) if links else set()
    for link in links:
        stage = link.stage.value
        if stage not in lifecycle.MANUFACTURING_STAGES:
            continue
        sub = latest_submission(db, link.supplier_id, link.stage)
        if sub is None:
            if stage in factory_stages:
                continue  # the factory's own batch data already covers it
            issues.append(Issue("info", "supplier_no_data",
                                f"{link.supplier.name} ({stage}) has not submitted data — "
                                f"default factors used", f"supplier:{link.supplier_id}"))
            continue
        for input_type, per_kg in submission_intensity(sub).items():
            _check_intensity(issues, stage, input_type, per_kg, f"Supplier {link.supplier.name}")

    # --- Life-cycle scenario completeness -----------------------------------
    settings = lifecycle_settings(db, product)
    included = lifecycle.BOUNDARIES.get(settings.boundary, [])
    if "distribution" in included and not settings.distribution:
        issues.append(Issue("warning", "no_distribution",
                            "Boundary includes distribution but no transport legs are set",
                            f"product:{product.sku}"))
    if "use" in included and not settings.washes:
        issues.append(Issue("warning", "no_use_scenario",
                            "Boundary includes the use phase but no wash count is set",
                            f"product:{product.sku}"))
    return issues
