from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from datetime import datetime, timedelta
from ..database import get_db
from ..models import User, Factory, ProductionRecord, Chemical, Report
from ..schemas import DashboardSummary, DashboardAlert
from ..utils.auth import get_current_user
from ..services.carbon_calculator import CarbonCalculator
from ..utils.constants import RESTRICTED_CAS_NUMBERS

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard summary with key metrics and alerts"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    # Current month date range
    now = datetime.now()
    start_of_month = datetime(now.year, now.month, 1)
    end_of_month = now

    # Carbon footprint this month
    carbon_summary = CarbonCalculator.calculate_summary(
        db, factory.id, start_of_month, end_of_month
    )
    carbon_this_month = carbon_summary.total_carbon_kg

    # Water usage this month
    records_this_month = db.query(ProductionRecord).filter(
        ProductionRecord.factory_id == factory.id,
        ProductionRecord.date >= start_of_month,
        ProductionRecord.date <= end_of_month
    ).all()

    water_this_month = sum(r.water_liters for r in records_this_month)

    # Chemical compliance percentage
    chemicals = db.query(Chemical).filter(Chemical.factory_id == factory.id).all()
    total_chemicals = len(chemicals)
    compliant_chemicals = sum(1 for c in chemicals if c.reach_compliant and c.zdhc_compliant)
    compliance_percentage = (compliant_chemicals / total_chemicals * 100) if total_chemicals > 0 else 0

    # Reports generated
    reports_count = db.query(func.count(Report.id)).filter(
        Report.factory_id == factory.id
    ).scalar()

    # Generate alerts
    alerts = []

    # Check for non-compliant chemicals
    non_compliant_count = total_chemicals - compliant_chemicals
    if non_compliant_count > 0:
        alerts.append(DashboardAlert(
            type="chemical_compliance",
            severity="high",
            message=f"{non_compliant_count} chemical(s) are not REACH & ZDHC compliant. Update compliance status."
        ))

    # Check for restricted substances
    restricted_chemicals = [c for c in chemicals if c.cas_number in RESTRICTED_CAS_NUMBERS]
    if restricted_chemicals:
        alerts.append(DashboardAlert(
            type="chemical_compliance",
            severity="high",
            message=f"{len(restricted_chemicals)} restricted substance(s) detected. Immediate action required."
        ))

    # Check for missing data this month
    if not records_this_month:
        alerts.append(DashboardAlert(
            type="missing_data",
            severity="medium",
            message="No production data logged for current month. Log data to track your sustainability metrics."
        ))

    # Check for expired certificates
    expired_certificates = [c for c in chemicals if c.expiry_date and c.expiry_date < now]
    if expired_certificates:
        alerts.append(DashboardAlert(
            type="chemical_compliance",
            severity="medium",
            message=f"{len(expired_certificates)} chemical certificate(s) have expired. Update certificates."
        ))

    # Check for data from previous month
    last_month = start_of_month - timedelta(days=1)
    start_of_last_month = datetime(last_month.year, last_month.month, 1)
    end_of_last_month = datetime(last_month.year, last_month.month, 1) + timedelta(days=32)
    end_of_last_month = end_of_last_month.replace(day=1) - timedelta(days=1)

    records_last_month = db.query(ProductionRecord).filter(
        ProductionRecord.factory_id == factory.id,
        ProductionRecord.date >= start_of_last_month,
        ProductionRecord.date <= end_of_last_month
    ).first()

    if not records_last_month and now.day > 5:
        alerts.append(DashboardAlert(
            type="missing_data",
            severity="low",
            message="No production data found for previous month. Consider generating a report."
        ))

    return DashboardSummary(
        carbon_footprint_this_month=carbon_this_month,
        water_usage_this_month=water_this_month,
        chemical_compliance_percentage=compliance_percentage,
        reports_generated=reports_count,
        alerts=alerts
    )
