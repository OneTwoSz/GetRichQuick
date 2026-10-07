"""
Suppliers — the upstream supply chain map (Phase 3).

Tier 2–4 facilities (fabric mills, dye houses, spinners, fibre sources,
trims vendors) with location and certifications, plus the login-free
supplier data link: the factory mints a token URL, the supplier posts a
period's facility totals, and the life-cycle engine turns them into
primary-data intensities for that stage.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    STAGE_TIER,
    DataQuality,
    Factory,
    ProductSupplier,
    Supplier,
    SupplierDataRequest,
    SupplierSubmission,
    User,
)
from ..schemas import (
    SupplierCreate,
    SupplierDataRequestCreate,
    SupplierDataRequestResponse,
    SupplierResponse,
    SupplierSubmissionCreate,
    SupplierSubmissionResponse,
)
from ..services.audit_logger import AuditLogger
from ..config import settings
from ..utils import links
from ..utils.auth import get_current_user
from ..utils.timeutil import utcnow

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])
# Public, login-free router for the supplier data link.
supplier_data_router = APIRouter(prefix="/supplier-data", tags=["Supplier data link"])


def _factory_for(user: User, db: Session) -> Factory:
    factory = db.query(Factory).filter(Factory.user_id == user.id).first()
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found — set up your factory first",
        )
    return factory


def _get_supplier(supplier_id: int, factory: Factory, db: Session) -> Supplier:
    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.factory_id == factory.id
    ).first()
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return supplier


def _supplier_fields(payload: SupplierCreate) -> dict:
    data = payload.model_dump()
    data["country"] = data["country"].upper()
    data["tier"] = data["tier"] or STAGE_TIER[payload.stage]
    return data


@router.get("", response_model=List[SupplierResponse])
def list_suppliers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    return (
        db.query(Supplier)
        .filter(Supplier.factory_id == factory.id)
        .order_by(Supplier.tier.desc(), Supplier.name)
        .all()
    )


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    supplier = Supplier(factory_id=factory.id, **_supplier_fields(payload))
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="CREATE", entity_type="supplier", entity_id=supplier.id,
        new_value=_supplier_fields(payload),
    )
    return supplier


@router.put("/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: int,
    payload: SupplierCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    supplier = _get_supplier(supplier_id, factory, db)
    old_value = AuditLogger.model_to_dict(supplier)
    for field, value in _supplier_fields(payload).items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="UPDATE", entity_type="supplier", entity_id=supplier.id,
        old_value=old_value, new_value=_supplier_fields(payload),
    )
    return supplier


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    supplier_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    supplier = _get_supplier(supplier_id, factory, db)
    if db.query(ProductSupplier).filter(ProductSupplier.supplier_id == supplier.id).count():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supplier is linked to products — unlink it first",
        )
    old_value = AuditLogger.model_to_dict(supplier)
    db.query(SupplierDataRequest).filter(SupplierDataRequest.supplier_id == supplier.id).delete()
    db.delete(supplier)
    db.commit()
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="DELETE", entity_type="supplier", entity_id=supplier_id,
        old_value=old_value,
    )


@router.post("/{supplier_id}/data-requests", response_model=SupplierDataRequestResponse,
             status_code=status.HTTP_201_CREATED)
def create_data_request(
    supplier_id: int,
    payload: SupplierDataRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mint a login-free link the supplier opens to submit their data."""
    factory = _factory_for(current_user, db)
    supplier = _get_supplier(supplier_id, factory, db)
    request = SupplierDataRequest(
        factory_id=factory.id, supplier_id=supplier.id,
        stage=payload.stage or supplier.stage, token=links.new_token(),
        period_label=payload.period_label, created_by=current_user.id,
        expires_at=links.expiry(payload.expires_in_days or settings.SUPPLIER_LINK_DAYS),
        max_submissions=settings.SUPPLIER_MAX_SUBMISSIONS,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return _request_out(request, db)


def _submission_count(request: SupplierDataRequest, db: Session) -> int:
    return db.query(SupplierSubmission).filter(SupplierSubmission.request_id == request.id).count()


def _request_out(request: SupplierDataRequest, db: Session) -> SupplierDataRequestResponse:
    out = SupplierDataRequestResponse.model_validate(request)
    out.submissions = _submission_count(request, db)
    return out


@router.delete("/{supplier_id}/data-requests/{request_id}", response_model=SupplierDataRequestResponse)
def revoke_data_request(
    supplier_id: int,
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stop a supplier data link working immediately (its submissions stay)."""
    factory = _factory_for(current_user, db)
    supplier = _get_supplier(supplier_id, factory, db)
    request = db.query(SupplierDataRequest).filter(
        SupplierDataRequest.id == request_id, SupplierDataRequest.supplier_id == supplier.id
    ).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    if request.revoked_at is None:
        request.revoked_at = utcnow()
        db.commit()
        db.refresh(request)
    return _request_out(request, db)


@router.get("/{supplier_id}/data-requests", response_model=List[SupplierDataRequestResponse])
def list_data_requests(
    supplier_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    supplier = _get_supplier(supplier_id, factory, db)
    rows = (
        db.query(SupplierDataRequest)
        .filter(SupplierDataRequest.supplier_id == supplier.id)
        .order_by(SupplierDataRequest.created_at.desc())
        .all()
    )
    return [_request_out(r, db) for r in rows]


@router.get("/{supplier_id}/submissions", response_model=List[SupplierSubmissionResponse])
def list_submissions(
    supplier_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    supplier = _get_supplier(supplier_id, factory, db)
    return (
        db.query(SupplierSubmission)
        .filter(SupplierSubmission.supplier_id == supplier.id)
        .order_by(SupplierSubmission.created_at.desc(), SupplierSubmission.id.desc())
        .all()
    )


# --- public supplier data link --------------------------------------------------


def _request_for(token: str, db: Session) -> SupplierDataRequest:
    request = db.query(SupplierDataRequest).filter(SupplierDataRequest.token == token).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    links.ensure_usable(expires_at=request.expires_at, revoked=request.revoked_at is not None)
    return request


@supplier_data_router.get("/{token}")
def supplier_request_info(token: str, http: Request, db: Session = Depends(get_db)):
    """What the supplier sees when they open the link: who is asking, for
    which stage and period — nothing about the factory's other data."""
    links.throttle_lookup(http, "supplier")
    request = _request_for(token, db)
    used = _submission_count(request, db)
    factory = db.query(Factory).filter(Factory.id == request.factory_id).first()
    return {
        "factory_name": factory.name if factory else None,
        "supplier_name": request.supplier.name,
        "stage": request.stage.value,
        "period_label": request.period_label,
        "already_submitted": used > 0,
        "expires_at": request.expires_at,
        "submissions_left": (None if request.max_submissions is None
                             else max(request.max_submissions - used, 0)),
    }


@supplier_data_router.post("/{token}", status_code=status.HTTP_201_CREATED)
def supplier_submit(
    token: str,
    payload: SupplierSubmissionCreate,
    http: Request,
    db: Session = Depends(get_db),
):
    """Supplier posts facility totals for the period. Re-submitting adds a
    new row; the engine uses the latest, and the history stays auditable."""
    links.throttle_lookup(http, "supplier")
    request = _request_for(token, db)
    links.ensure_submissions_left(_submission_count(request, db), request.max_submissions)
    links.throttle_submit(http, "supplier")
    data = payload.model_dump()
    data["data_quality"] = DataQuality(data["data_quality"])
    data["period_label"] = data["period_label"] or request.period_label
    row = SupplierSubmission(
        request_id=request.id, supplier_id=request.supplier_id, stage=request.stage, **data,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    AuditLogger.log_action(
        db=db, factory_id=request.factory_id, user_id=request.created_by,
        action="CREATE", entity_type="supplier_submission", entity_id=row.id,
        new_value={**payload.model_dump(), "supplier_id": request.supplier_id,
                   "stage": request.stage.value},
    )
    return {"status": "ok", "submission_id": row.id}
