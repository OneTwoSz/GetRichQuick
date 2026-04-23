from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from typing import List
from datetime import datetime, timedelta
from ..database import get_db
from ..models import User, Factory, ProductionRecord
from ..schemas import WaterEnergyTrends, WaterEnergyMetrics
from ..utils.auth import get_current_user

router = APIRouter(prefix="/water-energy", tags=["Water & Energy"])


@router.get("/trends", response_model=WaterEnergyTrends)
async def get_water_energy_trends(
    months: int = Query(6, ge=1, le=12, description="Number of months to retrieve"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get water and energy usage trends for the past N months"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=months * 30)

    # Get production records grouped by month
    records = db.query(
        extract('year', ProductionRecord.date).label('year'),
        extract('month', ProductionRecord.date).label('month'),
        func.sum(ProductionRecord.water_liters).label('total_water'),
        func.sum(ProductionRecord.electricity_kwh).label('total_electricity'),
        func.sum(ProductionRecord.garments_produced).label('total_garments')
    ).filter(
        ProductionRecord.factory_id == factory.id,
        ProductionRecord.date >= start_date,
        ProductionRecord.date <= end_date
    ).group_by(
        extract('year', ProductionRecord.date),
        extract('month', ProductionRecord.date)
    ).order_by(
        extract('year', ProductionRecord.date),
        extract('month', ProductionRecord.date)
    ).all()

    # Format results
    metrics_list = []
    for record in records:
        water_per_garment = record.total_water / record.total_garments if record.total_garments > 0 else 0
        electricity_per_garment = record.total_electricity / record.total_garments if record.total_garments > 0 else 0

        month_name = datetime(int(record.year), int(record.month), 1).strftime('%b %Y')

        metrics_list.append(WaterEnergyMetrics(
            month=month_name,
            water_per_garment_liters=round(water_per_garment, 2),
            electricity_per_garment_kwh=round(electricity_per_garment, 3),
            total_water_liters=round(record.total_water, 2),
            total_electricity_kwh=round(record.total_electricity, 2)
        ))

    return WaterEnergyTrends(metrics=metrics_list)
