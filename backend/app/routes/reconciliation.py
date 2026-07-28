"""
Monthly utility entry + the single-meter reconciliation (§4 of the phase-2
spec): monthly bill totals minus batch-attributed inputs equals facility
overhead, spread across the month's output by mass. Factories with zero
sub-metering simply log no batch inputs for power/water and run "overhead
only" — everything allocated top-down, tagged as the lower data-quality
tier.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Factory, MonthlyUtility, User
from ..schemas import (
    BatchOverheadOut,
    MonthlyUtilityCreate,
    MonthlyUtilityResponse,
    ReconciliationResponse,
)
from ..services import batch_carbon
from ..services.audit_logger import AuditLogger
from ..utils.auth import get_current_user

router = APIRouter(prefix="/utilities", tags=["Monthly Utilities"])


def _factory_for(user: User, db: Session) -> Factory:
    factory = db.query(Factory).filter(Factory.user_id == user.id).first()
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found — set up your factory first",
        )
    return factory


@router.get("", response_model=List[MonthlyUtilityResponse])
def list_monthly_utilities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    return (
        db.query(MonthlyUtility)
        .filter(MonthlyUtility.factory_id == factory.id)
        .order_by(MonthlyUtility.year.desc(), MonthlyUtility.month.desc())
        .all()
    )


@router.post("", response_model=MonthlyUtilityResponse,
             status_code=status.HTTP_201_CREATED)
def upsert_monthly_utility(
    payload: MonthlyUtilityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update the bill totals for a month (one row per month)."""
    factory = _factory_for(current_user, db)
    entry = (
        db.query(MonthlyUtility)
        .filter(
            MonthlyUtility.factory_id == factory.id,
            MonthlyUtility.year == payload.year,
            MonthlyUtility.month == payload.month,
        )
        .first()
    )
    if entry:
        old_value = AuditLogger.model_to_dict(entry)
        for key, value in payload.model_dump().items():
            setattr(entry, key, value)
        db.commit()
        db.refresh(entry)
        AuditLogger.log_action(
            db=db, factory_id=factory.id, user_id=current_user.id,
            action="UPDATE", entity_type="monthly_utility", entity_id=entry.id,
            old_value=old_value, new_value=AuditLogger.model_to_dict(entry),
        )
        return entry

    entry = MonthlyUtility(factory_id=factory.id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="CREATE", entity_type="monthly_utility", entity_id=entry.id,
        new_value=AuditLogger.model_to_dict(entry),
    )
    return entry


@router.get("/reconcile/{year}/{month}", response_model=ReconciliationResponse)
def reconcile_month(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The reconciliation view: bill totals, batch-attributed sums, the
    overhead remainder, and how it spreads across the month's batches."""
    factory = _factory_for(current_user, db)
    recon = batch_carbon.monthly_reconciliation(db, factory.id, year, month)
    if recon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No monthly utility entry for {year}-{month:02d} — enter the bill totals first",
        )
    recon["per_batch"] = {
        batch_id: BatchOverheadOut(**values)
        for batch_id, values in recon["per_batch"].items()
    }
    return ReconciliationResponse(**recon)
