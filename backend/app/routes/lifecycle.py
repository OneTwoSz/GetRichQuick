"""
Product life-cycle footprint, scenarios, validation, supply-chain links and
Digital Product Passports (Phase 3).

Authenticated endpoints live under /products/{id}/… next to the Phase 1
catalog routes; the public passport (and its QR code) under /passport.
"""
import hashlib
import io
import secrets
from pathlib import Path
from typing import List, Literal, Optional

import segno
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import (
    Factory,
    PassportVersion,
    Product,
    ProductLifecycle,
    ProductPassport,
    ProductSupplier,
    Supplier,
    SupplyChainStage,
    User,
)
from ..schemas import (
    CareSymbolsUpdate,
    ProductResponse,
    LifecycleFootprintResponse,
    LifecycleSettings,
    PassportPublishRequest,
    PassportStatusResponse,
    PassportVersionSummary,
    ProductSupplierLink,
    ProductSupplierResponse,
    PublicPassportResponse,
    ScenarioRequest,
    ScenarioResponse,
    StageResultOut,
    ValidationIssueOut,
    ValidationResponse,
)
from ..services import lifecycle, passport as passport_service, product_footprint
from ..services.audit_logger import AuditLogger
from ..services.signing_service import SigningError
from ..services.validation import validate_product
from ..utils import care_symbols
from ..utils.auth import get_current_user

router = APIRouter(prefix="/products", tags=["Product life cycle"])
# Public, login-free: what the QR code on the garment label resolves to.
passport_router = APIRouter(prefix="/passport", tags=["Digital Product Passport"])
# Public: product photos shown on passports.
media_router = APIRouter(prefix="/media", tags=["Media"])

# Accepted photo formats, identified by their leading bytes (not the
# client-supplied content type).
_IMAGE_SIGNATURES = {
    bytes.fromhex("ffd8ff"): "jpg",
    bytes.fromhex("89504e470d0a1a0a"): "png",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _get_product(product_id: int, user: User, db: Session) -> Product:
    factory = db.query(Factory).filter(Factory.user_id == user.id).first()
    if factory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Factory not found — set up your factory first")
    product = db.query(Product).filter(
        Product.id == product_id, Product.factory_id == factory.id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def _footprint_out(product: Product, result: lifecycle.LifecycleResult) -> LifecycleFootprintResponse:
    return LifecycleFootprintResponse(
        product_id=product.id,
        sku=product.sku,
        boundary=result.boundary,
        co2e_kg=result.co2e_kg,
        water_l=result.water_l,
        energy_kwh=result.energy_kwh,
        quality_mix=result.quality_mix,
        primary_share_pct=result.primary_share_pct,
        stages=[StageResultOut(**{k: v for k, v in vars(s).items() if k != "contributions"})
                for s in result.stages],
        mass_flow=result.mass_flow,
        excluded_stages=result.excluded_stages,
    )


@router.get("/{product_id}/footprint", response_model=LifecycleFootprintResponse)
def product_lifecycle_footprint(
    product_id: int,
    boundary: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per-garment life-cycle footprint by stage, with the data source and
    MEASURED/ESTIMATED/DEFAULT_FACTOR mix of every stage."""
    product = _get_product(product_id, current_user, db)
    if boundary and boundary not in lifecycle.BOUNDARIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown boundary")
    return _footprint_out(product, product_footprint.product_footprint(db, product, boundary))


@router.post("/{product_id}/footprint/scenario", response_model=ScenarioResponse)
def product_scenario(
    product_id: int,
    payload: ScenarioRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ecodesign comparison: baseline vs. a what-if (fibre swap, moving a
    stage to another country, different shipping, use/end-of-life)."""
    product = _get_product(product_id, current_user, db)
    unknown = [s for s in payload.stage_countries if s not in lifecycle.MANUFACTURING_STAGES
               and s != "raw_materials"]
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Unknown stage(s): {', '.join(unknown)}")
    inputs = product_footprint.build_inputs(db, product)
    if payload.boundary:
        inputs.boundary = payload.boundary
    base = lifecycle.compute(inputs)
    alt = lifecycle.compute(product_footprint.apply_scenario(inputs, payload))
    return ScenarioResponse(
        baseline=_footprint_out(product, base),
        scenario=_footprint_out(product, alt),
        delta_co2e_kg=round(alt.co2e_kg - base.co2e_kg, 4),
        delta_co2e_pct=round((alt.co2e_kg - base.co2e_kg) / base.co2e_kg * 100, 1) if base.co2e_kg else None,
        delta_water_l=round(alt.water_l - base.water_l, 2),
    )


@router.get("/{product_id}/lifecycle", response_model=LifecycleSettings)
def get_lifecycle_settings(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = _get_product(product_id, current_user, db)
    return product_footprint.lifecycle_settings(db, product)


@router.put("/{product_id}/lifecycle", response_model=LifecycleSettings)
def put_lifecycle_settings(
    product_id: int,
    payload: LifecycleSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = _get_product(product_id, current_user, db)
    row = db.query(ProductLifecycle).filter(ProductLifecycle.product_id == product.id).first()
    if row is None:
        row = ProductLifecycle(product_id=product.id)
        db.add(row)
    data = payload.model_dump()
    data["use_country"] = data["use_country"].upper()
    for field, value in data.items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    AuditLogger.log_action(
        db=db, factory_id=product.factory_id, user_id=current_user.id,
        action="UPDATE", entity_type="product_lifecycle", entity_id=product.id, new_value=data,
    )
    return row


@router.get("/{product_id}/validation", response_model=ValidationResponse)
def product_validation(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = _get_product(product_id, current_user, db)
    issues = validate_product(db, product)
    counts = {sev: sum(1 for i in issues if i.severity == sev) for sev in ("error", "warning", "info")}
    return ValidationResponse(
        product_id=product.id, errors=counts["error"], warnings=counts["warning"],
        infos=counts["info"], publishable=counts["error"] == 0,
        issues=[ValidationIssueOut(**vars(i)) for i in issues],
    )


# --- supply-chain links ---------------------------------------------------------


@router.get("/{product_id}/suppliers", response_model=List[ProductSupplierResponse])
def list_product_suppliers(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = _get_product(product_id, current_user, db)
    return db.query(ProductSupplier).filter(ProductSupplier.product_id == product.id).all()


@router.put("/{product_id}/suppliers", response_model=ProductSupplierResponse)
def link_product_supplier(
    product_id: int,
    payload: ProductSupplierLink,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set (or replace) the supplier for one stage of this product."""
    product = _get_product(product_id, current_user, db)
    supplier = db.query(Supplier).filter(
        Supplier.id == payload.supplier_id, Supplier.factory_id == product.factory_id
    ).first()
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    link = db.query(ProductSupplier).filter(
        ProductSupplier.product_id == product.id, ProductSupplier.stage == payload.stage
    ).first()
    if link is None:
        link = ProductSupplier(product_id=product.id, stage=payload.stage, supplier_id=supplier.id)
        db.add(link)
    else:
        link.supplier_id = supplier.id
    db.commit()
    db.refresh(link)
    AuditLogger.log_action(
        db=db, factory_id=product.factory_id, user_id=current_user.id,
        action="UPDATE", entity_type="product_supplier", entity_id=product.id,
        new_value={"stage": payload.stage.value, "supplier_id": supplier.id},
    )
    return link


@router.delete("/{product_id}/suppliers/{stage}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_product_supplier(
    product_id: int,
    stage: SupplyChainStage,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = _get_product(product_id, current_user, db)
    link = db.query(ProductSupplier).filter(
        ProductSupplier.product_id == product.id, ProductSupplier.stage == stage
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No supplier for that stage")
    db.delete(link)
    db.commit()
    AuditLogger.log_action(
        db=db, factory_id=product.factory_id, user_id=current_user.id,
        action="DELETE", entity_type="product_supplier", entity_id=product.id,
        old_value={"stage": stage.value},
    )


# --- passports --------------------------------------------------------------------


@router.get("/{product_id}/passport", response_model=PassportStatusResponse)
def passport_status(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = _get_product(product_id, current_user, db)
    passport = db.query(ProductPassport).filter(ProductPassport.product_id == product.id).first()
    if passport is None:
        return PassportStatusResponse(product_id=product.id)
    return PassportStatusResponse(
        product_id=product.id, public_token=passport.public_token,
        versions=[PassportVersionSummary.model_validate(v) for v in reversed(passport.versions)],
    )


@router.post("/{product_id}/passport/publish", response_model=PassportStatusResponse,
             status_code=status.HTTP_201_CREATED)
def publish_passport(
    product_id: int,
    payload: PassportPublishRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the automated checks, record the named sign-off, then hash and
    sign an immutable new passport version."""
    product = _get_product(product_id, current_user, db)
    try:
        row = passport_service.publish(
            db, product, current_user, reviewed_by=payload.reviewed_by_name,
            review_note=payload.review_note,
            disclose_supplier_names=payload.disclose_supplier_names,
        )
    except passport_service.PublishBlocked as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Automated checks found errors — fix them before publishing",
                    "issues": [vars(i) for i in exc.issues]},
        )
    except SigningError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Signing failed: {exc}")
    AuditLogger.log_action(
        db=db, factory_id=product.factory_id, user_id=current_user.id,
        action="CREATE", entity_type="passport_version", entity_id=row.id,
        new_value={"product_id": product.id, "version": row.version,
                   "payload_hash": row.payload_hash, "reviewed_by": row.reviewed_by_name},
    )
    return passport_status(product_id, current_user, db)


def _public_passport(token: str, db: Session) -> ProductPassport:
    passport = db.query(ProductPassport).filter(ProductPassport.public_token == token).first()
    if not passport or not passport.versions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passport not found")
    return passport


@passport_router.get("/{token}", response_model=PublicPassportResponse)
def public_passport(token: str, version: Optional[int] = None, db: Session = Depends(get_db)):
    """The published passport (latest, or a specific version), with a
    fresh hash + signature check so the page can show whether the content
    is exactly what the factory signed."""
    passport = _public_passport(token, db)
    rows = passport.versions
    row: Optional[PassportVersion] = rows[-1] if version is None else next(
        (v for v in rows if v.version == version), None)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return PublicPassportResponse(
        version=row.version, published_at=row.published_at, payload=row.payload,
        payload_hash=row.payload_hash, algorithm=row.algorithm,
        signature_b64=row.signature_b64, public_key_pem=row.public_key_pem,
        verification=passport_service.verify_version(row),
        versions=[PassportVersionSummary.model_validate(v) for v in reversed(rows)],
    )


@passport_router.get("/{token}/qr.svg")
def passport_qr(
    token: str,
    ecc: Literal["m", "q", "h"] = "m",
    db: Session = Depends(get_db),
):
    """QR code for the garment label / hangtag, pointing at the public page.

    `ecc=q` (25% recovery) or `h` (30%) suits labels printed on fabric that
    get washed and creased. The 4-module quiet zone is the QR spec minimum;
    scanners struggle when printers crop it."""
    _public_passport(token, db)
    url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/passport/{token}"
    # A standalone SVG document (with xmlns) — svg_inline() omits the
    # namespace, which <img> tags and label printers refuse to render.
    buffer = io.BytesIO()
    segno.make(url, error=ecc).save(buffer, kind="svg", scale=6, border=4, xmldecl=False)
    return Response(content=buffer.getvalue(), media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600"})


# --- passport presentation: photo and care symbols ---------------------------------


def _media_dir() -> Path:
    path = Path(settings.MEDIA_DIR).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _remove_media(url: Optional[str]):
    if url and url.startswith("/api/media/"):
        (_media_dir() / url.rsplit("/", 1)[-1]).unlink(missing_ok=True)


@router.post("/{product_id}/image", response_model=ProductResponse)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the product photo shown at the top of its passport (JPEG/PNG, ≤ 5 MB)."""
    product = _get_product(product_id, current_user, db)
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 5 MB or smaller")
    ext = next((e for sig, e in _IMAGE_SIGNATURES.items() if data.startswith(sig)), None)
    if ext is None and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = "webp"
    if ext is None:
        raise HTTPException(status_code=400, detail="Upload a JPEG, PNG or WebP image")

    name = f"{secrets.token_hex(12)}.{ext}"
    (_media_dir() / name).write_bytes(data)
    _remove_media(product.image_url)
    product.image_url = f"/api/media/{name}"
    product.image_sha256 = hashlib.sha256(data).hexdigest()
    db.commit()
    db.refresh(product)
    AuditLogger.log_action(
        db=db, factory_id=product.factory_id, user_id=current_user.id,
        action="UPDATE", entity_type="product_image", entity_id=product.id,
        new_value={"image_url": product.image_url, "image_sha256": product.image_sha256},
    )
    return product


@router.delete("/{product_id}/image", response_model=ProductResponse)
def delete_product_image(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = _get_product(product_id, current_user, db)
    _remove_media(product.image_url)
    product.image_url = None
    product.image_sha256 = None
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}/care-symbols", response_model=ProductResponse)
def set_care_symbols(
    product_id: int,
    payload: CareSymbolsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Care-label symbols for the passport — at most one per category."""
    product = _get_product(product_id, current_user, db)
    try:
        product.care_symbols = care_symbols.validate(payload.symbols)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    db.commit()
    db.refresh(product)
    AuditLogger.log_action(
        db=db, factory_id=product.factory_id, user_id=current_user.id,
        action="UPDATE", entity_type="product_care_symbols", entity_id=product.id,
        new_value={"care_symbols": product.care_symbols},
    )
    return product


@media_router.get("/{name}")
def get_media(name: str):
    """Public product photos. Names are random, so they can't be enumerated."""
    path = (_media_dir() / name).resolve()
    if path.parent != _media_dir() or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})
