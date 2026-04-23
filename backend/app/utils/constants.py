"""
Emission factors for carbon footprint calculation
All values in kg CO2 equivalent
"""

# Fabric emission factors (kg CO2 per kg of fabric)
FABRIC_EMISSION_FACTORS = {
    "cotton": 5.5,
    "organic_cotton": 3.8,
    "polyester": 7.0,
    "blend": 6.2,  # cotton-poly blend
}

# Other emission factors
ELECTRICITY_EMISSION_FACTOR = 0.85  # kg CO2 per kWh (India grid)
WATER_TREATMENT_EMISSION_FACTOR = 0.3  # kg CO2 per 1000 liters
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
