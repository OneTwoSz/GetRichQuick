"""
Digital Product Passport — build, sign, publish, verify (Phase 3).

A passport version is an immutable snapshot of what the factory is willing
to state publicly about a product: identity, composition, supply chain
(by stage, tier and country), the life-cycle footprint with its data-
quality disclosure, circularity and chemical-compliance facts, and who
reviewed it.

Publishing runs the verification gates in order:
  1. automated checks (services/validation.py) — any error blocks
  2. named human sign-off (reviewed_by_name, required)
  3. canonical-JSON hash + signature with the factory's key — the same
     key and scheme as signed reports (services/signing_service.py)

Reading a passport re-hashes the stored payload and re-verifies the
signature, so a row edited in the database after publishing shows up as
tampered on the public page.

The field set follows the content the EU's JRC has proposed for textile
DPPs (identity, composition, origin by stage, environmental footprint,
circularity, substances of concern) — the delegated act is not final, so
`schema` is versioned and the payload can grow.
"""
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..models import (
    STAGE_TIER,
    BatchInputType,
    Chemical,
    Factory,
    MaterialCategory,
    Order,
    PassportVersion,
    Product,
    ProductPassport,
    ProductSupplier,
    SupplyChainStage,
    User,
)
from ..utils import care_symbols
from ..utils.hashing import sha256_of_json
from . import lifecycle
from .product_footprint import build_inputs, lifecycle_settings
from .signing_service import SigningError, get_or_create_active_key, sign_payload_hash, verify_signature
from .validation import validate_product

SCHEMA = "greenthread.dpp/v1"


class PublishBlocked(Exception):
    def __init__(self, issues):
        super().__init__("automated checks found errors")
        self.issues = issues


def get_or_create_passport(db: Session, product: Product) -> ProductPassport:
    passport = db.query(ProductPassport).filter(ProductPassport.product_id == product.id).first()
    if passport is None:
        passport = ProductPassport(factory_id=product.factory_id, product_id=product.id,
                                   public_token=secrets.token_urlsafe(12))
        db.add(passport)
        db.flush()
    return passport


def _composition(product: Product) -> List[Dict]:
    fibres = [i for i in product.bom_items if i.category == MaterialCategory.FIBER]
    total = sum(i.quantity_per_garment_g for i in fibres)
    return [
        {"material": i.material_name, "material_key": i.material_key,
         "share_pct": round(i.quantity_per_garment_g / total * 100, 1) if total else None}
        for i in fibres
    ]


def _supply_chain(db: Session, product: Product, factory: Factory, disclose_names: bool) -> List[Dict]:
    links = {l.stage: l for l in db.query(ProductSupplier)
             .filter(ProductSupplier.product_id == product.id).all()}
    chain = []
    for stage in SupplyChainStage:
        link = links.get(stage)
        if link:
            s = link.supplier
            chain.append({
                "stage": stage.value, "tier": s.tier,
                "facility": s.name if disclose_names else None,
                "city": s.city, "country": s.country,
                "certifications": [c.get("name") for c in (s.certifications or []) if c.get("name")],
            })
        elif stage == SupplyChainStage.ASSEMBLY:
            chain.append({"stage": stage.value, "tier": STAGE_TIER[stage], "facility": factory.name,
                          "city": factory.location, "country": "IN", "certifications": []})
    return chain


def _chemical_compliance(db: Session, product: Product) -> Dict:
    """Chemicals drawn by the batches behind this product's orders."""
    chem_ids = set()
    for order in db.query(Order).filter(Order.product_id == product.id).all():
        for alloc in order.allocations:
            for b in [alloc.batch, *alloc.batch.reworks]:
                for i in b.inputs:
                    if i.chemical_id and i.input_type in (BatchInputType.CHEMICAL_KG, BatchInputType.DYE_KG):
                        chem_ids.add(i.chemical_id)
    chems = db.query(Chemical).filter(Chemical.id.in_(chem_ids)).all() if chem_ids else []
    return {
        "chemicals_traced": len(chems),
        "zdhc_mrsl_conformant": sum(1 for c in chems if c.zdhc_compliant),
        "reach_compliant": sum(1 for c in chems if c.reach_compliant),
    }


def _stage_out(r: lifecycle.StageResult) -> Dict:
    return {"stage": r.stage, "label": r.label, "co2e_kg": round(r.co2e_kg, 4),
            "water_l": round(r.water_l, 2), "data_source": r.data_source,
            "quality_mix": r.quality_mix, "country": r.country}


def build_payload(db: Session, product: Product, factory: Factory, *, version: int,
                  token: str, reviewed_by: str, review_note: Optional[str],
                  disclose_supplier_names: bool, issues) -> Dict:
    result = lifecycle.compute(build_inputs(db, product))
    settings = lifecycle_settings(db, product)
    return {
        "schema": SCHEMA,
        "passport_id": token,
        "version": version,
        "published_at": datetime.now(timezone.utc),
        "product": {
            "sku": product.sku, "name": product.name, "description": product.description,
            "fiber_composition": product.fiber_composition,
            "garment_weight_g": product.garment_weight_g,
            "care_instructions": product.care_instructions,
            "care_symbols": care_symbols.describe(product.care_symbols or []),
            # The photo's hash is signed with the rest of the passport, so a
            # swapped image is detectable even though the file lives outside.
            "image_url": product.image_url,
            "image_sha256": product.image_sha256,
        },
        "manufacturer": {"name": factory.name, "location": factory.location, "country": "IN"},
        "composition": _composition(product),
        "supply_chain": _supply_chain(db, product, factory, disclose_supplier_names),
        "footprint": {
            "functional_unit": "1 garment",
            "boundary": result.boundary,
            "co2e_kg": result.co2e_kg,
            "water_l": result.water_l,
            "energy_kwh": result.energy_kwh,
            "primary_data_share_pct": result.primary_share_pct,
            "quality_mix": result.quality_mix,
            "stages": [_stage_out(r) for r in result.stages],
            "excluded_stages": result.excluded_stages,
            "methodology": (
                "ISO 14040/44-aligned attributional model. Factory stages from batch-level "
                "primary data allocated per ISO 14044 (mass by default); upstream stages from "
                "supplier submissions where available, otherwise disclosed default factors."
            ),
        },
        "circularity": {
            "recycled_content_pct": product.recycled_content_pct,
            "cutting_waste_pct": product.cutting_waste_percent,
            "cutting_waste_destination": (factory.cutting_waste_destination.value
                                          if factory.cutting_waste_destination else None),
            "end_of_life_scenario": settings.end_of_life,
        },
        "chemical_compliance": _chemical_compliance(db, product),
        "verification": {
            "automated_checks": {
                "errors": sum(1 for i in issues if i.severity == "error"),
                "warnings": sum(1 for i in issues if i.severity == "warning"),
            },
            "reviewed_by": reviewed_by,
            "review_note": review_note,
        },
    }


def publish(db: Session, product: Product, user: User, *, reviewed_by: str,
            review_note: Optional[str] = None, disclose_supplier_names: bool = False) -> PassportVersion:
    issues = validate_product(db, product)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        raise PublishBlocked(errors)

    factory = db.query(Factory).filter(Factory.id == product.factory_id).first()
    passport = get_or_create_passport(db, product)
    version = (passport.versions[-1].version + 1) if passport.versions else 1
    payload = build_payload(db, product, factory, version=version, token=passport.public_token,
                            reviewed_by=reviewed_by, review_note=review_note,
                            disclose_supplier_names=disclose_supplier_names, issues=issues)
    payload_hash = sha256_of_json(payload)
    key = get_or_create_active_key(db, factory)
    signed = sign_payload_hash(key, payload_hash)

    row = PassportVersion(
        passport_id=passport.id, version=version, payload=payload, payload_hash=payload_hash,
        factory_key_id=key.id, algorithm=signed.algorithm, signature_b64=signed.signature_b64,
        public_key_pem=signed.public_key_pem, reviewed_by_name=reviewed_by,
        review_note=review_note, published_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def verify_version(row: PassportVersion) -> Dict:
    """Recompute the hash of the stored payload and check the signature."""
    recomputed = sha256_of_json(row.payload)
    hash_ok = recomputed == row.payload_hash
    try:
        sig_ok = verify_signature(row.public_key_pem, row.algorithm, row.signature_b64, row.payload_hash)
    except SigningError:
        sig_ok = False
    return {"hash_matches": hash_ok, "signature_valid": sig_ok,
            "verified": hash_ok and sig_ok, "payload_hash": row.payload_hash,
            "recomputed_hash": recomputed}
