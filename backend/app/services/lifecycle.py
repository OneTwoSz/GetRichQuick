"""
Product life-cycle engine — pure, deterministic, no I/O (Phase 3).

Computes a per-garment footprint across the whole life cycle, stage by
stage, resolving every stage through a data hierarchy and recording which
rung it landed on:

    factory primary (allocated batch data)  → MEASURED / ESTIMATED as logged
    supplier submission (token link)        → the submission's tier
    supplier-declared factor (BOM override) → ESTIMATED
    library default (utils/factor_library)  → DEFAULT_FACTOR

The mass flow runs backwards from the finished garment so every upstream
stage is charged for the material it actually had to produce, including
cutting waste, knitting loss and spinning loss:

    fabric = garment ÷ (1 − cutting waste)
    yarn   = fabric  ÷ (1 − knitting loss)
    fibre  = yarn × fibre share ÷ (1 − that fibre's spinning loss)

Boundaries (ISO 14040/44 system boundary, disclosed on every result):
    cradle_to_gate      raw materials → trims & packaging
    cradle_to_customer  + distribution
    cradle_to_grave     + use phase + end of life

BOM dye and chemical lines are deliberately NOT counted as materials: the
wet-processing stage already charges chemical and dye inputs, and counting
both would double count.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..models import DataQuality
from ..utils import factor_library as fl
from .allocation import QualityContribution, data_quality_mix

STAGES: List[Tuple[str, str]] = [
    ("raw_materials", "Raw materials (fibre)"),
    ("yarn_production", "Yarn production (spinning)"),
    ("fabric_production", "Fabric production (knitting)"),
    ("wet_processing", "Wet processing (bleach, dye, print, finish)"),
    ("assembly", "Assembly (cutting & sewing)"),
    ("trims_packaging", "Trims & packaging"),
    ("distribution", "Distribution"),
    ("use", "Use phase (washing)"),
    ("end_of_life", "End of life"),
]
STAGE_LABELS = dict(STAGES)
MANUFACTURING_STAGES = ("yarn_production", "fabric_production", "wet_processing", "assembly")

BOUNDARIES = {
    "cradle_to_gate": ["raw_materials", *MANUFACTURING_STAGES, "trims_packaging"],
    "cradle_to_customer": ["raw_materials", *MANUFACTURING_STAGES, "trims_packaging", "distribution"],
    "cradle_to_grave": [s for s, _ in STAGES],
}


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FibreLine:
    material_key: Optional[str]
    net_g: float                              # fibre in the finished garment
    declared_co2e_per_kg: Optional[float] = None  # supplier EPD / override


@dataclass(frozen=True)
class MaterialLine:
    """A trim or packaging line, per garment."""
    material_key: Optional[str]
    grams: float
    declared_co2e_per_kg: Optional[float] = None


@dataclass(frozen=True)
class StageActivity:
    """Primary data for one stage, already expressed per garment (the DB
    layer divides allocated order footprints by units)."""
    co2e_kg: float
    water_l: float
    energy_kwh: float
    quality_amounts: Dict[DataQuality, float]  # co2e split by tier
    source: str


@dataclass(frozen=True)
class SupplierIntensity:
    """A supplier's submitted resource use per kg of the stage's output."""
    inputs_per_kg: Dict[str, float]  # input_type -> quantity per kg output
    quality: DataQuality
    source: str
    country: Optional[str] = None


@dataclass(frozen=True)
class TransportLeg:
    mode: str
    distance_km: float


@dataclass
class LifecycleInputs:
    garment_weight_g: float
    cutting_waste_percent: float = 0.0
    fibres: List[FibreLine] = field(default_factory=list)
    trims: List[MaterialLine] = field(default_factory=list)
    packaging: List[MaterialLine] = field(default_factory=list)
    factory_country: str = fl.DEFAULT_COUNTRY
    # Where each upstream stage physically happens (from linked suppliers).
    # Missing stages are assumed to run in the factory's country.
    stage_countries: Dict[str, str] = field(default_factory=dict)
    factory_primary: Dict[str, StageActivity] = field(default_factory=dict)
    supplier_intensities: Dict[str, SupplierIntensity] = field(default_factory=dict)
    distribution: List[TransportLeg] = field(default_factory=list)
    boundary: str = "cradle_to_gate"
    washes: int = 0
    tumble_dry: bool = False
    use_country: str = "EU"
    end_of_life: str = "eu_average"


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@dataclass
class StageResult:
    stage: str
    label: str
    co2e_kg: float
    water_l: float
    energy_kwh: float
    # factory_primary | factory_default | supplier_primary | supplier_declared | default | mixed
    data_source: str
    quality_mix: Dict[str, float]
    sources: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    country: Optional[str] = None
    mass_kg: Optional[float] = None
    # Unrounded per-tier CO2e, used to build the overall mix exactly.
    contributions: List[QualityContribution] = field(default_factory=list, repr=False)


@dataclass
class LifecycleResult:
    boundary: str
    stages: List[StageResult]
    co2e_kg: float
    water_l: float
    energy_kwh: float
    quality_mix: Dict[str, float]
    primary_share_pct: float   # MEASURED + ESTIMATED share of CO2e
    mass_flow: Dict[str, float]
    excluded_stages: List[str]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class _StageAccumulator:
    def __init__(self, stage: str, country: Optional[str] = None, mass_kg: Optional[float] = None):
        self.stage = stage
        self.country = country
        self.mass_kg = mass_kg
        self.co2e = 0.0
        self.water = 0.0
        self.energy = 0.0
        self.contributions: List[QualityContribution] = []
        self.sources: List[str] = []
        self.flags: List[str] = []
        self.kinds: set = set()

    def add(self, co2e: float, quality: DataQuality, kind: str, source: str,
            water: float = 0.0, energy: float = 0.0):
        self.co2e += co2e
        self.water += water
        self.energy += energy
        self.contributions.append(QualityContribution(amount=co2e, quality=quality))
        self.kinds.add(kind)
        if source not in self.sources:
            self.sources.append(source)

    def result(self) -> StageResult:
        kind = next(iter(self.kinds)) if len(self.kinds) == 1 else ("mixed" if self.kinds else "none")
        return StageResult(
            stage=self.stage,
            label=STAGE_LABELS[self.stage],
            co2e_kg=round(self.co2e, 5),
            water_l=round(self.water, 3),
            energy_kwh=round(self.energy, 4),
            data_source=kind,
            quality_mix=data_quality_mix(self.contributions),
            sources=self.sources,
            flags=self.flags,
            country=self.country,
            mass_kg=round(self.mass_kg, 5) if self.mass_kg is not None else None,
            contributions=list(self.contributions),
        )


def _apply_inputs(acc: _StageAccumulator, inputs: Dict[str, float], scale_kg: float,
                  country: Optional[str], quality: DataQuality, kind: str, source: str):
    """Charge resource inputs (per kg) × scale to a stage, electricity at
    the stage country's grid factor."""
    for input_type, per_kg in inputs.items():
        qty = per_kg * scale_kg
        if input_type == "electricity_kwh":
            g = fl.grid_factor(country)
            acc.add(qty * g.co2e, quality, kind, source, energy=qty)
        else:
            f = fl.INPUT_FACTORS.get(input_type)
            if f is None:
                acc.flags.append(f"unknown_input:{input_type}")
                continue
            acc.add(qty * f.co2e, quality, kind, source, water=qty * f.water_l)


def mass_flow(inputs: LifecycleInputs) -> Dict[str, float]:
    """kg of fabric, yarn and each fibre needed per finished garment."""
    if not 0 <= inputs.cutting_waste_percent < 100:
        raise ValueError("cutting_waste_percent must be in [0, 100)")
    garment_kg = inputs.garment_weight_g / 1000.0
    fabric_kg = garment_kg / (1 - inputs.cutting_waste_percent / 100)
    yarn_kg = fabric_kg / (1 - fl.KNITTING_LOSS)
    flow = {"garment_kg": garment_kg, "fabric_kg": fabric_kg, "yarn_kg": yarn_kg}
    fibres = _fibres(inputs)
    total_net = sum(f.net_g for f in fibres)
    fibre_total = 0.0
    for i, f in enumerate(fibres):
        share = f.net_g / total_net if total_net > 0 else 1.0 / len(fibres)
        loss = fl.SPINNING_LOSS.get(f.material_key or "", fl.DEFAULT_SPINNING_LOSS)
        kg = yarn_kg * share / (1 - loss)
        flow[f"fibre_kg[{i}:{f.material_key or 'unspecified'}]"] = kg
        fibre_total += kg
    flow["fibre_kg_total"] = fibre_total
    return flow


def _fibres(inputs: LifecycleInputs) -> List[FibreLine]:
    # No fibre lines: assume the whole garment is an unspecified fibre so
    # the stage is never silently zero.
    return inputs.fibres or [FibreLine(material_key=None, net_g=inputs.garment_weight_g)]


def compute(inputs: LifecycleInputs) -> LifecycleResult:
    if inputs.boundary not in BOUNDARIES:
        raise ValueError(f"unknown boundary {inputs.boundary}")
    if inputs.garment_weight_g <= 0:
        raise ValueError("garment_weight_g must be positive")

    included = BOUNDARIES[inputs.boundary]
    flow = mass_flow(inputs)
    garment_kg, fabric_kg, yarn_kg = flow["garment_kg"], flow["fabric_kg"], flow["yarn_kg"]
    stage_out_kg = {
        "yarn_production": yarn_kg,
        "fabric_production": fabric_kg,
        "wet_processing": fabric_kg,
        "assembly": fabric_kg,
    }
    results: Dict[str, StageResult] = {}

    # 1. Raw materials
    acc = _StageAccumulator("raw_materials", inputs.stage_countries.get("raw_materials"),
                            flow["fibre_kg_total"])
    fibres = _fibres(inputs)
    total_net = sum(f.net_g for f in fibres)
    for f in fibres:
        share = f.net_g / total_net if total_net > 0 else 1.0 / len(fibres)
        loss = fl.SPINNING_LOSS.get(f.material_key or "", fl.DEFAULT_SPINNING_LOSS)
        kg = yarn_kg * share / (1 - loss)
        lib = fl.FIBRE_FACTORS.get(f.material_key or "")
        water_factor = (lib or fl.FIBRE_FALLBACK).water_l
        if f.declared_co2e_per_kg is not None:
            acc.add(kg * f.declared_co2e_per_kg, DataQuality.ESTIMATED, "supplier_declared",
                    f"supplier-declared factor for {f.material_key or 'fibre'}",
                    water=kg * water_factor)
        elif lib:
            acc.add(kg * lib.co2e, DataQuality.DEFAULT_FACTOR, "default",
                    f"{lib.source}: {lib.key}", water=kg * lib.water_l)
        else:
            acc.add(kg * fl.FIBRE_FALLBACK.co2e, DataQuality.DEFAULT_FACTOR, "default",
                    f"{fl.FIBRE_FALLBACK.source}: generic fibre", water=kg * fl.FIBRE_FALLBACK.water_l)
            acc.flags.append(f"unknown_fibre:{f.material_key or 'unspecified'}")
    results["raw_materials"] = acc.result()

    # 2–5. Manufacturing stages
    for stage in MANUFACTURING_STAGES:
        country = inputs.stage_countries.get(stage) or inputs.factory_country
        acc = _StageAccumulator(stage, country, stage_out_kg[stage])
        primary = inputs.factory_primary.get(stage)
        supplier = inputs.supplier_intensities.get(stage)
        if primary is not None:
            acc.co2e = primary.co2e_kg
            acc.water = primary.water_l
            acc.energy = primary.energy_kwh
            acc.contributions = [QualityContribution(amount=v, quality=q)
                                 for q, v in primary.quality_amounts.items()]
            # Batches that ran on built-in defaults (an outsourced lot with
            # no submission yet) are factory data, but not primary data.
            has_primary = any(v > 0 for q, v in primary.quality_amounts.items()
                              if q != DataQuality.DEFAULT_FACTOR)
            acc.kinds.add("factory_primary" if has_primary else "factory_default")
            acc.sources.append(primary.source)
            acc.country = inputs.factory_country
        elif supplier is not None:
            acc.country = supplier.country or country
            _apply_inputs(acc, supplier.inputs_per_kg, stage_out_kg[stage], acc.country,
                          supplier.quality, "supplier_primary", supplier.source)
        else:
            _apply_inputs(acc, fl.STAGE_DEFAULT_INPUTS[stage], stage_out_kg[stage], country,
                          DataQuality.DEFAULT_FACTOR, "default",
                          f"{fl.REFERENCE_SET}: default {stage} inputs")
        results[stage] = acc.result()

    # 6. Trims & packaging
    acc = _StageAccumulator("trims_packaging")
    for line in inputs.trims:
        kg = line.grams / 1000.0
        lib = fl.TRIM_FACTORS.get(line.material_key or "")
        if line.declared_co2e_per_kg is not None:
            acc.add(kg * line.declared_co2e_per_kg, DataQuality.ESTIMATED, "supplier_declared",
                    f"supplier-declared factor for {line.material_key or 'trim'}")
        elif lib:
            acc.add(kg * lib.co2e, DataQuality.DEFAULT_FACTOR, "default", f"{lib.source}: {lib.key}")
        else:
            acc.add(kg * fl.TRIM_FALLBACK.co2e, DataQuality.DEFAULT_FACTOR, "default",
                    f"{fl.TRIM_FALLBACK.source}: generic trim")
            acc.flags.append(f"unknown_trim:{line.material_key or 'unspecified'}")
    for line in inputs.packaging:
        kg = line.grams / 1000.0
        lib = fl.PACKAGING_FACTORS.get(line.material_key or "")
        if line.declared_co2e_per_kg is not None:
            acc.add(kg * line.declared_co2e_per_kg, DataQuality.ESTIMATED, "supplier_declared",
                    f"supplier-declared factor for {line.material_key or 'packaging'}")
        elif lib:
            acc.add(kg * lib.co2e, DataQuality.DEFAULT_FACTOR, "default", f"{lib.source}: {lib.key}")
        else:
            acc.flags.append(f"unknown_packaging:{line.material_key or 'unspecified'}")
    results["trims_packaging"] = acc.result()

    # 7. Distribution — shipped mass is garment + packaging.
    shipped_kg = garment_kg + sum(p.grams for p in inputs.packaging) / 1000.0
    acc = _StageAccumulator("distribution", mass_kg=shipped_kg)
    for leg in inputs.distribution:
        f = fl.TRANSPORT_FACTORS.get(leg.mode)
        if f is None:
            acc.flags.append(f"unknown_transport_mode:{leg.mode}")
            continue
        tkm = shipped_kg / 1000.0 * leg.distance_km
        acc.add(tkm * f.co2e, DataQuality.DEFAULT_FACTOR, "default",
                f"{f.source}: {leg.mode} per tkm")
    if not inputs.distribution and "distribution" in included:
        acc.flags.append("no_transport_legs")
    results["distribution"] = acc.result()

    # 8. Use phase
    acc = _StageAccumulator("use", inputs.use_country, garment_kg)
    if inputs.washes > 0:
        loads = inputs.washes * garment_kg / fl.WASH_LOAD["load_kg"]
        kwh = loads * (fl.WASH_LOAD["electricity_kwh"]
                       + (fl.TUMBLE_DRY_KWH_PER_LOAD if inputs.tumble_dry else 0.0))
        water = loads * fl.WASH_LOAD["water_l"]
        g = fl.grid_factor(inputs.use_country)
        acc.add(kwh * g.co2e + water * fl.INPUT_FACTORS["water_l"].co2e,
                DataQuality.DEFAULT_FACTOR, "default",
                f"{fl.REFERENCE_SET}: {inputs.washes} washes, {inputs.use_country} grid",
                water=water, energy=kwh)
    elif "use" in included:
        acc.flags.append("no_wash_scenario")
    results["use"] = acc.result()

    # 9. End of life
    acc = _StageAccumulator("end_of_life", mass_kg=garment_kg)
    eol = fl.END_OF_LIFE_FACTORS.get(inputs.end_of_life) or fl.END_OF_LIFE_FACTORS["eu_average"]
    acc.add(garment_kg * eol.co2e, DataQuality.DEFAULT_FACTOR, "default",
            f"{eol.source}: {eol.key}")
    results["end_of_life"] = acc.result()

    stages = [results[s] for s, _ in STAGES if s in included]
    mix = data_quality_mix([c for r in stages for c in r.contributions])
    return LifecycleResult(
        boundary=inputs.boundary,
        stages=stages,
        co2e_kg=round(sum(r.co2e_kg for r in stages), 4),
        water_l=round(sum(r.water_l for r in stages), 2),
        energy_kwh=round(sum(r.energy_kwh for r in stages), 3),
        quality_mix=mix,
        primary_share_pct=round(mix[DataQuality.MEASURED.value] + mix[DataQuality.ESTIMATED.value], 2),
        mass_flow={k: round(v, 5) for k, v in flow.items()},
        excluded_stages=[s for s, _ in STAGES if s not in included],
    )
