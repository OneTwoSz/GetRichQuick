from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from ..models import User, Factory
from ..schemas import CarbonSummary
from ..utils.auth import get_current_user
from ..services.carbon_calculator import CarbonCalculator

router = APIRouter(prefix="/carbon", tags=["Carbon Footprint"])


@router.get("/summary", response_model=CarbonSummary)
async def get_carbon_summary(
    date_from: datetime = Query(..., description="Start date"),
    date_to: datetime = Query(..., description="End date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get carbon footprint summary for a date range"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    summary = CarbonCalculator.calculate_summary(db, factory.id, date_from, date_to)
    return summary


@router.get("/breakdown", response_model=CarbonSummary)
async def get_carbon_breakdown(
    date_from: datetime = Query(..., description="Start date"),
    date_to: datetime = Query(..., description="End date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get carbon footprint breakdown by category for a date range"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    summary = CarbonCalculator.calculate_summary(db, factory.id, date_from, date_to)
    return summary
