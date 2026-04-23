from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from ..database import get_db
from ..models import User, Factory, AuditLog
from ..schemas import AuditLogResponse
from ..utils.auth import get_current_user

router = APIRouter(prefix="/audit-log", tags=["Audit Log"])


@router.get("", response_model=List[AuditLogResponse])
async def get_audit_logs(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    limit: int = Query(100, le=1000, description="Maximum number of records"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get audit log entries for current factory"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    query = db.query(AuditLog).filter(AuditLog.factory_id == factory.id)

    # Apply filters
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)

    if date_from:
        query = query.filter(AuditLog.timestamp >= date_from)

    if date_to:
        query = query.filter(AuditLog.timestamp <= date_to)

    # Order by most recent first and apply limit
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

    return logs
