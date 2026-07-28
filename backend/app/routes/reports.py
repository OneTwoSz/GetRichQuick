from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import os
from ..database import get_db
from ..models import User, Factory, Report
from ..schemas import ReportCreate, ReportResponse
from ..utils.auth import get_current_user
from ..utils.hashing import canonical_json, sha256_hex
from ..services.report_generator import ReportGenerator
from ..services.carbon_calculator import CarbonCalculator
from ..services.signing_service import sign_report, SigningError
from ..config import settings

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/generate", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(
    report_data: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a sustainability report PDF"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    # Calculate carbon summary for the report
    carbon_summary = CarbonCalculator.calculate_summary(
        db, factory.id, report_data.date_from, report_data.date_to
    )

    # Calculate water per garment
    from ..models import ProductionRecord
    records = db.query(ProductionRecord).filter(
        ProductionRecord.factory_id == factory.id,
        ProductionRecord.date >= report_data.date_from,
        ProductionRecord.date <= report_data.date_to
    ).all()

    total_water = sum(r.water_liters for r in records)
    total_garments = carbon_summary.total_garments
    water_per_garment = total_water / total_garments if total_garments > 0 else 0

    # Generate PDF
    pdf_filename = ReportGenerator.generate_pdf_report(
        db, factory.id, report_data.date_from, report_data.date_to
    )

    # Build canonical payload and hash it — signature is computed over this
    # exact byte sequence. Anything that could change the interpretation of
    # the PDF (totals, inputs, date range, records) MUST be in here.
    payload = {
        "factory": {
            "id": factory.id,
            "name": factory.name,
            "location": factory.location,
            "gst_number": factory.gst_number,
        },
        "report_type": report_data.report_type.value
            if hasattr(report_data.report_type, "value") else str(report_data.report_type),
        "date_from": report_data.date_from,
        "date_to": report_data.date_to,
        "totals": {
            "total_carbon_kg": carbon_summary.total_carbon_kg,
            "carbon_per_garment_kg": carbon_summary.carbon_per_garment_kg,
            "water_per_garment_liters": water_per_garment,
            "total_water_liters": total_water,
            "total_garments": total_garments,
        },
        "production_records": [
            {
                "id": r.id,
                "date": r.date,
                "fabric_type": r.fabric_type,
                "fabric_quantity_kg": r.fabric_quantity_kg,
                "dye_quantity_kg": r.dye_quantity_kg,
                "chemicals_kg": r.chemicals_kg,
                "electricity_kwh": r.electricity_kwh,
                "water_liters": r.water_liters,
                "wastewater_treated_liters": r.wastewater_treated_liters,
                "garments_produced": r.garments_produced,
                "transport_distance_km": r.transport_distance_km,
                "transport_mode": r.transport_mode,
            }
            for r in records
        ],
        # Phase 2: the Allocation Statement is part of what the signature
        # attests to — method per batch, shares, and the data-quality mix.
        "allocation_statement": ReportGenerator.batch_allocation_data(
            db, factory.id, report_data.date_from, report_data.date_to
        ),
    }
    payload_hash = sha256_hex(canonical_json(payload))

    # Save report metadata to database
    new_report = Report(
        factory_id=factory.id,
        report_type=report_data.report_type,
        date_from=report_data.date_from,
        date_to=report_data.date_to,
        total_carbon_kg=carbon_summary.total_carbon_kg,
        carbon_per_garment_kg=carbon_summary.carbon_per_garment_kg,
        water_per_garment_liters=water_per_garment,
        pdf_url=pdf_filename,
        payload_hash=payload_hash,
        generated_by=current_user.id
    )

    db.add(new_report)
    db.flush()  # populate new_report.id before signing

    # Sign. Failures here degrade to "unsigned report" rather than blocking
    # the PDF, but are loudly logged so ops notices missing signatures.
    try:
        sign_report(db, factory, new_report)
    except SigningError as err:
        import logging
        logging.getLogger(__name__).error(
            "signing failed for report=%s: %s", new_report.id, err
        )

    db.commit()
    db.refresh(new_report)

    return new_report


@router.get("", response_model=List[ReportResponse])
async def get_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all reports for current factory"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    reports = db.query(Report).filter(
        Report.factory_id == factory.id
    ).order_by(Report.created_at.desc()).all()

    return reports


@router.get("/{report_id}/download")
async def download_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download a report PDF"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    report = db.query(Report).filter(
        Report.id == report_id,
        Report.factory_id == factory.id
    ).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    # Get PDF file path. If the PDF doesn't exist (WeasyPrint missing in dev)
    # fall back to the rendered HTML sibling so the report is still viewable.
    pdf_path = os.path.join(settings.REPORTS_DIR, report.pdf_url)

    if not os.path.exists(pdf_path):
        html_path = pdf_path[:-4] + ".html" if pdf_path.endswith(".pdf") else pdf_path
        if os.path.exists(html_path):
            return FileResponse(
                html_path,
                media_type="text/html",
                filename=os.path.basename(html_path),
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found"
        )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=report.pdf_url
    )
