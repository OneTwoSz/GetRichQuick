"""
Emission factors for carbon footprint calculation
All values in kg CO2 equivalent
"""
from .factor_library import GRID_FACTORS, INPUT_FACTORS

# Fabric emission factors (kg CO2 per kg of fabric)
FABRIC_EMISSION_FACTORS = {
    "cotton": 5.5,
    "organic_cotton": 3.8,
    "polyester": 7.0,
    "blend": 6.2,  # cotton-poly blend
}

# Other emission factors
ELECTRICITY_EMISSION_FACTOR = GRID_FACTORS["IN"].co2e  # kg CO2 per kWh (CEA, India grid)
WATER_TREATMENT_EMISSION_FACTOR = 0.17088  # kg CO2e per 1000 L (DESNZ 2025 water treatment)
DYE_CHEMICAL_EMISSION_FACTOR = 2.5  # kg CO2 per kg

# Transport emission factors (kg CO2 per km)
TRANSPORT_EMISSION_FACTORS = {
    "truck": 0.1,
    "sea_freight": 0.016,
}

# Restricted substances for REACH/ZDHC compliance
# Simplified list - in production, this would be a comprehensive database
RESTRICTED_CHEMICALS = [
    # Azo dyes that release restricted amines
    {"cas": "92-67-1", "name": "4-Aminobiphenyl", "reason": "Carcinogenic"},
    {"cas": "95-69-2", "name": "4-Chloro-o-toluidine", "reason": "Carcinogenic"},
    {"cas": "106-47-8", "name": "4-Chloroaniline", "reason": "Toxic"},
    # Heavy metals
    {"cas": "7439-92-1", "name": "Lead", "reason": "Heavy metal"},
    {"cas": "7440-43-9", "name": "Cadmium", "reason": "Heavy metal"},
    {"cas": "7439-97-6", "name": "Mercury", "reason": "Heavy metal"},
    # Phthalates
    {"cas": "117-81-7", "name": "DEHP", "reason": "Phthalate"},
    {"cas": "84-74-2", "name": "DBP", "reason": "Phthalate"},
    # Add more as needed
]

# Get list of restricted CAS numbers for quick lookup
RESTRICTED_CAS_NUMBERS = {item["cas"] for item in RESTRICTED_CHEMICALS}


# ---------------------------------------------------------------------------
# Per-material emission factors used by Product / BOM rollups
# ---------------------------------------------------------------------------
#
# Looked up by `BillOfMaterialsItem.material_key`. When the key isn't in the
# table, the per-category fallback below is used. All values are kg CO2e per
# kg of material. These are simplified industry averages (Higg MSI / PEF
# textile method) — fine for a Tier-1 supplier compliance tool, not a full
# LCA. A factory can override a single line with `carbon_factor_override`.
MATERIAL_CARBON_FACTORS = {
    # Fibers
    "cotton": 5.5,
    "organic_cotton": 3.8,
    "polyester": 7.0,
    "recycled_polyester": 3.5,
    "blend": 6.2,
    "elastane": 6.5,
    "viscose": 4.5,
    "wool": 12.0,
    "linen": 2.8,
    # Wet processing chemistry
    "reactive_dye": 4.5,
    "disperse_dye": 6.0,
    "acid_dye": 5.0,
    "sodium_carbonate": 0.6,
    "glauber_salt": 0.3,
    "caustic_soda": 1.1,
    "softener": 2.0,
    # Trims (small per-garment quantities, generic averages)
    "button": 3.0,
    "label": 2.5,
    "zipper": 4.5,
    "sewing_thread": 5.5,
}

# Per-category fallbacks used when material_key is unknown.
MATERIAL_CATEGORY_FALLBACK_FACTORS = {
    "fiber": 5.5,        # default to conventional cotton
    "dye": 5.0,
    "chemical": 1.5,
    "trim": 3.5,
}


# ---------------------------------------------------------------------------
# Phase 2 — batch input emission factors & per-process defaults
# ---------------------------------------------------------------------------

# kg CO2e per unit of each BatchInputType. Keyed by enum value. Derived
# from the factor library (see its docstring for sources) so batch-level
# order footprints and product life-cycle footprints use identical numbers.
BATCH_INPUT_EMISSION_FACTORS = {
    "electricity_kwh": GRID_FACTORS["IN"].co2e,  # CEA India grid
    **{key: f.co2e for key, f in INPUT_FACTORS.items()},
}

# DEFAULT_FACTOR tier (§5 of the phase-2 spec): per-process consumption per
# kg of fabric, used when a batch — typically an outsourced dye lot — has no
# measured or bill-derived inputs at all. Values are conservative textbook
# figures for South-Indian knitwear processing; anything computed from these
# is tagged DataQuality.DEFAULT_FACTOR so reports never pass it off as
# primary data.
PROCESS_DEFAULT_INPUT_FACTORS = {
    # process value -> { input_type value: quantity per kg fabric }
    "knitting": {"electricity_kwh": 0.75},
    "bleaching": {"water_l": 40.0, "electricity_kwh": 0.5, "chemical_kg": 0.3, "steam_kg": 1.0},
    "dyeing": {"water_l": 100.0, "electricity_kwh": 1.0, "chemical_kg": 0.5, "dye_kg": 0.03, "steam_kg": 2.0},
    "printing": {"water_l": 20.0, "electricity_kwh": 0.8, "dye_kg": 0.02},
    "finishing": {"water_l": 15.0, "electricity_kwh": 0.6, "steam_kg": 1.5},
    "cutting_sewing": {"electricity_kwh": 0.4},
}
