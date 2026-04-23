from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import Dict, List
from ..models import ProductionRecord, Factory
from ..utils.constants import (
    FABRIC_EMISSION_FACTORS,
    ELECTRICITY_EMISSION_FACTOR,
    WATER_TREATMENT_EMISSION_FACTOR,
    DYE_CHEMICAL_EMISSION_FACTOR,
    TRANSPORT_EMISSION_FACTORS,
)
from ..schemas import CarbonSummary, CarbonBreakdown


class CarbonCalculator:
    """Service for calculating carbon footprint from production data"""

    @staticmethod
    def calculate_record_emissions(record: ProductionRecord) -> Dict[str, float]:
        """Calculate emissions for a single production record"""

        # Materials (fabric) emissions
        fabric_factor = FABRIC_EMISSION_FACTORS.get(record.fabric_type.value, 0)
        materials_emissions = record.fabric_quantity_kg * fabric_factor

        # Energy emissions
        energy_emissions = record.electricity_kwh * ELECTRICITY_EMISSION_FACTOR

        # Water treatment emissions
        water_emissions = (record.wastewater_treated_liters / 1000) * WATER_TREATMENT_EMISSION_FACTOR

        # Chemicals emissions (dyes + other chemicals)
        chemical_emissions = (record.dye_quantity_kg + record.chemicals_kg) * DYE_CHEMICAL_EMISSION_FACTOR

        # Transport emissions
        transport_emissions = 0
        if record.transport_mode and record.transport_distance_km > 0:
            transport_factor = TRANSPORT_EMISSION_FACTORS.get(record.transport_mode.value, 0)
            transport_emissions = record.transport_distance_km * transport_factor

        total_emissions = (
            materials_emissions
            + energy_emissions
            + water_emissions
            + chemical_emissions
            + transport_emissions
        )

        return {
            "materials": materials_emissions,
            "energy": energy_emissions,
            "water_treatment": water_emissions,
            "chemicals": chemical_emissions,
            "transport": transport_emissions,
            "total": total_emissions,
        }

    @staticmethod
    def calculate_summary(
        db: Session,
        factory_id: int,
        date_from: datetime,
        date_to: datetime
    ) -> CarbonSummary:
        """Calculate carbon summary for a date range"""

        # Get all production records in date range
        records = db.query(ProductionRecord).filter(
            ProductionRecord.factory_id == factory_id,
            ProductionRecord.date >= date_from,
            ProductionRecord.date <= date_to
        ).all()

        if not records:
            return CarbonSummary(
                total_carbon_kg=0,
                carbon_per_garment_kg=0,
                breakdown=CarbonBreakdown(
                    materials=0,
                    energy=0,
                    water_treatment=0,
                    chemicals=0,
                    transport=0
                ),
                total_garments=0,
                date_from=date_from,
                date_to=date_to
            )

        # Calculate emissions for each record
        breakdown_totals = {
            "materials": 0,
            "energy": 0,
            "water_treatment": 0,
            "chemicals": 0,
            "transport": 0,
        }

        total_garments = 0
        total_carbon = 0

        for record in records:
            emissions = CarbonCalculator.calculate_record_emissions(record)
            breakdown_totals["materials"] += emissions["materials"]
            breakdown_totals["energy"] += emissions["energy"]
            breakdown_totals["water_treatment"] += emissions["water_treatment"]
            breakdown_totals["chemicals"] += emissions["chemicals"]
            breakdown_totals["transport"] += emissions["transport"]
            total_carbon += emissions["total"]
            total_garments += record.garments_produced

        carbon_per_garment = total_carbon / total_garments if total_garments > 0 else 0

        return CarbonSummary(
            total_carbon_kg=round(total_carbon, 2),
            carbon_per_garment_kg=round(carbon_per_garment, 3),
            breakdown=CarbonBreakdown(**{k: round(v, 2) for k, v in breakdown_totals.items()}),
            total_garments=total_garments,
            date_from=date_from,
            date_to=date_to
        )
