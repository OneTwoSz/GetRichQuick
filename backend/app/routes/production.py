from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from ..database import get_db
from ..models import User, Factory, ProductionRecord
from ..schemas import ProductionRecordCreate, ProductionRecordUpdate, ProductionRecordResponse
from ..utils.auth import get_current_user
from ..services.audit_logger import AuditLogger

router = APIRouter(prefix="/production", tags=["Production"])


@router.get("", response_model=List[ProductionRecordResponse])
async def get_production_records(
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2020),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get production records, optionally filtered by month and year"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    query = db.query(ProductionRecord).filter(ProductionRecord.factory_id == factory.id)

    # Filter by month and year if provided
    if month and year:
        from sqlalchemy import extract
        query = query.filter(
            extract('month', ProductionRecord.date) == month,
            extract('year', ProductionRecord.date) == year
        )
    elif year:
        from sqlalchemy import extract
        query = query.filter(extract('year', ProductionRecord.date) == year)

    records = query.order_by(ProductionRecord.date.desc()).all()
    return records


@router.post("", response_model=ProductionRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_production_record(
    record_data: ProductionRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new production record"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    # Create new production record
    new_record = ProductionRecord(
        factory_id=factory.id,
        created_by=current_user.id,
        **record_data.model_dump()
    )

    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    # Log to audit trail
    AuditLogger.log_action(
        db=db,
        factory_id=factory.id,
        user_id=current_user.id,
        action="CREATE",
        entity_type="production_record",
        entity_id=new_record.id,
        new_value=AuditLogger.model_to_dict(new_record)
    )

    return new_record


@router.put("/{record_id}", response_model=ProductionRecordResponse)
async def update_production_record(
    record_id: int,
    record_data: ProductionRecordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a production record"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    record = db.query(ProductionRecord).filter(
        ProductionRecord.id == record_id,
        ProductionRecord.factory_id == factory.id
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Production record not found"
        )

    # Store old values for audit
    old_value = AuditLogger.model_to_dict(record)

    # Update record
    for key, value in record_data.model_dump().items():
        setattr(record, key, value)

    db.commit()
    db.refresh(record)

    # Log to audit trail
    AuditLogger.log_action(
        db=db,
        factory_id=factory.id,
        user_id=current_user.id,
        action="UPDATE",
        entity_type="production_record",
        entity_id=record.id,
        old_value=old_value,
        new_value=AuditLogger.model_to_dict(record)
    )

    return record


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_production_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a production record"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    record = db.query(ProductionRecord).filter(
        ProductionRecord.id == record_id,
        ProductionRecord.factory_id == factory.id
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Production record not found"
        )

    # Store old values for audit
    old_value = AuditLogger.model_to_dict(record)

    # Delete record
    db.delete(record)
    db.commit()

    # Log to audit trail
    AuditLogger.log_action(
        db=db,
        factory_id=factory.id,
        user_id=current_user.id,
        action="DELETE",
        entity_type="production_record",
        entity_id=record_id,
        old_value=old_value
    )
