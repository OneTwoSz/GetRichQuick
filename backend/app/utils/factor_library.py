"""
Emission factor library for the product life-cycle engine (Phase 3).

Every factor carries its provenance so a footprint can say exactly which
number it used and where that number came from. This is the "secondary"
end of the four-tier hierarchy the life-cycle engine resolves through:

    1. MEASURED       — primary data from the factory's own batches or a
                        supplier's metered submission
    2. SUPPLIER       — supplier-declared value (EPD, BOM override, bill-
                        derived submission) → tagged ESTIMATED
    3. LIBRARY        — a factor from this module → tagged DEFAULT_FACTOR
    4. FALLBACK       — category-level generic from this module → also
                        DEFAULT_FACTOR, plus a flag on the stage

IMPORTANT — provenance of the values below: they are indicative midpoints
of ranges published in open textile LCA literature, collected as the
GreenThread reference set v1. They are the right order of magnitude for a
supplier-side compliance tool and are always disclosed as DEFAULT_FACTOR,
but they are NOT a licensed LCA dataset. Before a footprint is used in a
public claim (PEF, French Ecoscore, marketing), swap in a licensed source
(ecoinvent, Higg MSI, a supplier EPD) by adding factors with a proper
`source` — the engine and the passport print whatever `source` says.
"""
from dataclasses import dataclass
from typing import Dict, Optional

REFERENCE_SET = "GreenThread reference set v1 (indicative)"


@dataclass(frozen=True)
class Factor:
    key: str
    co2e: float           # kg CO2e per `unit`
    unit: str
    water_l: float = 0.0  # litres of water consumed per `unit`
    source: str = REFERENCE_SET
    note: str = ""


def _set(unit: str, rows: Dict[str, object], note: str = "") -> Dict[str, Factor]:
    """Build a factor table. Each row is either `co2e` or `(co2e, water_l)`."""
    out = {}
    for key, values in rows.items():
        co2e, water = values if isinstance(values, tuple) else (values, 0.0)
        out[key] = Factor(key=key, co2e=co2e, unit=unit, water_l=water, note=note)
    return out


# ---------------------------------------------------------------------------
# Stage 1 — raw materials: cradle-to-fibre-gate, per kg of fibre.
# (co2e kg/kg, water L/kg). Water is blue water; cotton's is dominated by
# irrigation and varies hugely by region — treat as indicative only.
# ---------------------------------------------------------------------------
FIBRE_FACTORS = _set("kg fibre", {
    "cotton": (2.0, 2500.0),
    "organic_cotton": (1.2, 1000.0),
    "recycled_cotton": (0.6, 50.0),
    "polyester": (3.4, 60.0),
    "recycled_polyester": (1.6, 30.0),
    "elastane": (9.0, 100.0),
    "nylon": (7.5, 150.0),
    "recycled_nylon": (2.5, 50.0),
    "viscose": (3.0, 400.0),
    "lyocell": (2.0, 300.0),
    "linen": (1.5, 300.0),
    "wool": (20.0, 500.0),
    "blend": (2.7, 1300.0),  # generic cotton/poly
}, note="cradle-to-fibre-gate")

# Used when a fiber BOM line has an unknown material_key (and flagged).
FIBRE_FALLBACK = Factor("unspecified_fibre", 2.7, "kg fibre", 1300.0,
                        note="generic fibre — add a material_key for a specific factor")

# Share of fibre lost as waste in spinning (comber noil, fly, sweepings).
# Fibre demand = yarn ÷ (1 − loss). Staple fibres lose far more than
# continuous filaments.
SPINNING_LOSS = {
    "cotton": 0.12, "organic_cotton": 0.12, "recycled_cotton": 0.15,
    "polyester": 0.03, "recycled_polyester": 0.04, "elastane": 0.02,
    "nylon": 0.03, "recycled_nylon": 0.04, "viscose": 0.05, "lyocell": 0.05,
    "linen": 0.15, "wool": 0.15, "blend": 0.08,
}
DEFAULT_SPINNING_LOSS = 0.08

# Yarn lost at the knitting machine. Yarn demand = fabric ÷ (1 − loss).
KNITTING_LOSS = 0.02


# ---------------------------------------------------------------------------
# Stages 2–5 — manufacturing. Defaults are per kg of that stage's OUTPUT,
# expressed as resource inputs so the engine can apply the supplier
# country's grid factor rather than a fixed CO2 number.
# ---------------------------------------------------------------------------
STAGE_DEFAULT_INPUTS: Dict[str, Dict[str, float]] = {
    # ring-spun yarn, per kg yarn
    "yarn_production": {"electricity_kwh": 3.5},
    # per kg fabric
    "fabric_production": {"electricity_kwh": 0.75},
    # dyeing-dominated default for a knit fabric, per kg fabric
    "wet_processing": {
        "water_l": 100.0, "electricity_kwh": 1.0, "chemical_kg": 0.5,
        "dye_kg": 0.03, "steam_kg": 2.0,
    },
    # per kg fabric entering the cutting table
    "assembly": {"electricity_kwh": 0.4},
}

# kg CO2e per unit of non-electric inputs. Electricity is looked up per
# country in GRID_FACTORS instead. Kept identical to the batch engine's
# BATCH_INPUT_EMISSION_FACTORS so factory-primary and default stages agree.
INPUT_FACTORS = {
    "water_l": Factor("water_l", 0.0003, "L", 1.0, note="treatment + supply"),
    "chemical_kg": Factor("chemical_kg", 2.5, "kg"),
    "dye_kg": Factor("dye_kg", 2.5, "kg"),
    "steam_kg": Factor("steam_kg", 0.18, "kg", note="boiler fuel mix, Tiruppur-typical"),
    "diesel_l": Factor("diesel_l", 2.68, "L", note="genset"),
}

# kg CO2e per kWh, by ISO-3166 alpha-2 country. "IN" is kept at the
# conservative 0.85 the rest of the app uses so batch-level and life-cycle
# numbers reconcile.
GRID_FACTORS = _set("kWh", {
    "IN": 0.85, "BD": 0.62, "CN": 0.58, "VN": 0.60, "PK": 0.45, "LK": 0.55,
    "ID": 0.75, "TR": 0.45, "KH": 0.60, "EG": 0.45, "PT": 0.20, "IT": 0.30,
    "DE": 0.38, "FR": 0.06, "GB": 0.20, "US": 0.37, "EU": 0.25,
}, note="grid average")
DEFAULT_COUNTRY = "IN"


def grid_factor(country: Optional[str]) -> Factor:
    code = (country or DEFAULT_COUNTRY).upper()
    return GRID_FACTORS.get(code) or GRID_FACTORS[DEFAULT_COUNTRY]


# ---------------------------------------------------------------------------
# Stage 6 — trims & packaging, per kg of material.
# ---------------------------------------------------------------------------
TRIM_FACTORS = _set("kg", {
    "button": 3.0, "label": 2.5, "zipper": 4.5, "sewing_thread": 5.5,
    "elastic_tape": 6.0, "hangtag": 1.0,
})
TRIM_FALLBACK = Factor("unspecified_trim", 3.5, "kg", note="generic trim")

PACKAGING_FACTORS = _set("kg", {
    "ldpe_polybag": 2.1, "recycled_ldpe_polybag": 1.0,
    "cardboard": 0.9, "paper": 1.0,
})


# ---------------------------------------------------------------------------
# Stage 7 — distribution, per tonne-km.
# ---------------------------------------------------------------------------
TRANSPORT_FACTORS = _set("tkm", {
    "truck": 0.105, "rail": 0.025, "sea_freight": 0.016, "air": 0.60,
})


# ---------------------------------------------------------------------------
# Stages 8–9 — use and end of life (cradle-to-grave only).
# ---------------------------------------------------------------------------
# One domestic wash load at 40°C. A garment's share of a load is its
# weight over the load weight.
WASH_LOAD = {"electricity_kwh": 0.5, "water_l": 50.0, "load_kg": 4.0}
TUMBLE_DRY_KWH_PER_LOAD = 2.0

END_OF_LIFE_FACTORS = _set("kg", {
    "eu_average": 0.8, "landfill": 0.5, "incineration": 1.5, "recycling": 0.2,
}, note="per kg of discarded garment")
