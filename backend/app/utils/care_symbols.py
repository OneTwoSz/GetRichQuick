"""
Garment care symbols, grouped the way care labels group them (washing,
bleaching, drying, ironing, professional care). A product carries at most
one symbol per category. Codes are stable identifiers stored on products
and in signed passports; the frontend draws the icons.
"""
from typing import Dict, List, Tuple

CATEGORIES = ("washing", "bleaching", "drying", "ironing", "professional")

# code -> (category, label)
CARE_SYMBOLS: Dict[str, Tuple[str, str]] = {
    "wash_30": ("washing", "Machine wash 30°C"),
    "wash_30_gentle": ("washing", "Machine wash 30°C, gentle cycle"),
    "wash_40": ("washing", "Machine wash 40°C"),
    "wash_60": ("washing", "Machine wash 60°C"),
    "hand_wash": ("washing", "Hand wash only"),
    "do_not_wash": ("washing", "Do not wash"),
    "bleach_any": ("bleaching", "Any bleach allowed"),
    "bleach_non_chlorine": ("bleaching", "Non-chlorine bleach only"),
    "do_not_bleach": ("bleaching", "Do not bleach"),
    "tumble_low": ("drying", "Tumble dry, low heat"),
    "tumble_normal": ("drying", "Tumble dry, normal heat"),
    "do_not_tumble": ("drying", "Do not tumble dry"),
    "line_dry": ("drying", "Line dry"),
    "dry_flat": ("drying", "Dry flat"),
    "iron_low": ("ironing", "Iron at low temperature (110°C)"),
    "iron_medium": ("ironing", "Iron at medium temperature (150°C)"),
    "iron_high": ("ironing", "Iron at high temperature (200°C)"),
    "do_not_iron": ("ironing", "Do not iron"),
    "dry_clean": ("professional", "Professional dry clean"),
    "do_not_dry_clean": ("professional", "Do not dry clean"),
}


def validate(codes: List[str]) -> List[str]:
    """Return the codes in category order, or raise ValueError."""
    unknown = [c for c in codes if c not in CARE_SYMBOLS]
    if unknown:
        raise ValueError(f"unknown care symbol(s): {', '.join(unknown)}")
    seen = {}
    for code in codes:
        category = CARE_SYMBOLS[code][0]
        if category in seen and seen[category] != code:
            raise ValueError(f"only one {category} symbol allowed ({seen[category]}, {code})")
        seen[category] = code
    return [seen[c] for c in CATEGORIES if c in seen]


def describe(codes: List[str]) -> List[dict]:
    return [{"code": c, "category": CARE_SYMBOLS[c][0], "label": CARE_SYMBOLS[c][1]}
            for c in codes if c in CARE_SYMBOLS]
