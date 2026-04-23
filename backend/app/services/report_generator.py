from sqlalchemy.orm import Session
from datetime import datetime
from weasyprint import HTML
from jinja2 import Template
import os
from typing import Dict
from ..models import Factory, ProductionRecord
from .carbon_calculator import CarbonCalculator


class ReportGenerator:
    """Service for generating PDF sustainability reports"""

    @staticmethod
    def generate_pdf_report(
        db: Session,
        factory_id: int,
        date_from: datetime,
        date_to: datetime
    ) -> str:
        """Generate a professional PDF sustainability report"""

        # Get factory details
        factory = db.query(Factory).filter(Factory.id == factory_id).first()

        # Calculate carbon summary
        carbon_summary = CarbonCalculator.calculate_summary(db, factory_id, date_from, date_to)

        # Get production records for additional metrics
        records = db.query(ProductionRecord).filter(
            ProductionRecord.factory_id == factory_id,
            ProductionRecord.date >= date_from,
            ProductionRecord.date <= date_to
        ).all()

        # Calculate water and energy metrics
        total_water = sum(r.water_liters for r in records)
        total_electricity = sum(r.electricity_kwh for r in records)
        total_garments = carbon_summary.total_garments

        water_per_garment = total_water / total_garments if total_garments > 0 else 0
        electricity_per_garment = total_electricity / total_garments if total_garments > 0 else 0

        # Get chemical compliance data
        from ..models import Chemical
        from ..utils.constants import RESTRICTED_CAS_NUMBERS

        chemicals = db.query(Chemical).filter(Chemical.factory_id == factory_id).all()
        total_chemicals = len(chemicals)
        compliant_chemicals = sum(1 for c in chemicals if c.reach_compliant and c.zdhc_compliant)
        non_compliant_chemicals = []

        for chem in chemicals:
            if chem.cas_number in RESTRICTED_CAS_NUMBERS:
                non_compliant_chemicals.append(chem.chemical_name)

        compliance_percentage = (compliant_chemicals / total_chemicals * 100) if total_chemicals > 0 else 0

        # Prepare data for template
        report_data = {
            "factory_name": factory.name,
            "factory_location": factory.location,
            "date_from": date_from.strftime("%d %B %Y"),
            "date_to": date_to.strftime("%d %B %Y"),
            "generated_date": datetime.now().strftime("%d %B %Y"),
            "total_carbon_kg": f"{carbon_summary.total_carbon_kg:,.2f}",
            "carbon_per_garment_kg": f"{carbon_summary.carbon_per_garment_kg:.3f}",
            "total_garments": f"{total_garments:,}",
            "total_water_liters": f"{total_water:,.2f}",
            "water_per_garment_liters": f"{water_per_garment:.2f}",
            "total_electricity_kwh": f"{total_electricity:,.2f}",
            "electricity_per_garment_kwh": f"{electricity_per_garment:.3f}",
            "materials_emissions": f"{carbon_summary.breakdown.materials:,.2f}",
            "energy_emissions": f"{carbon_summary.breakdown.energy:,.2f}",
            "water_emissions": f"{carbon_summary.breakdown.water_treatment:,.2f}",
            "chemicals_emissions": f"{carbon_summary.breakdown.chemicals:,.2f}",
            "transport_emissions": f"{carbon_summary.breakdown.transport:,.2f}",
            "chemical_compliance_percentage": f"{compliance_percentage:.1f}",
            "total_chemicals": total_chemicals,
            "compliant_chemicals": compliant_chemicals,
            "non_compliant_chemicals": non_compliant_chemicals,
        }

        # Generate HTML from template
        html_content = ReportGenerator._get_html_template(report_data)

        # Generate PDF
        reports_dir = "/app/reports"
        os.makedirs(reports_dir, exist_ok=True)

        filename = f"sustainability_report_{factory_id}_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.pdf"
        filepath = os.path.join(reports_dir, filename)

        HTML(string=html_content).write_pdf(filepath)

        return filename

    @staticmethod
    def _get_html_template(data: Dict) -> str:
        """Get HTML template for PDF report"""

        template_str = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Sustainability Report</title>
    <style>
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-family: 'Arial', sans-serif;
            color: #333;
            line-height: 1.6;
        }
        .header {
            text-align: center;
            border-bottom: 3px solid #0D9488;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #0D9488;
            margin: 0;
            font-size: 28px;
        }
        .header p {
            color: #666;
            margin: 5px 0;
        }
        .section {
            margin-bottom: 25px;
        }
        .section-title {
            background-color: #0D9488;
            color: white;
            padding: 10px;
            font-size: 18px;
            margin-bottom: 15px;
        }
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }
        .metric-box {
            border: 1px solid #ddd;
            padding: 15px;
            background-color: #f9f9f9;
        }
        .metric-label {
            color: #666;
            font-size: 12px;
            margin-bottom: 5px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #0D9488;
        }
        .metric-unit {
            font-size: 14px;
            color: #666;
        }
        .breakdown-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        .breakdown-table th,
        .breakdown-table td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        .breakdown-table th {
            background-color: #f0f0f0;
            font-weight: bold;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #ddd;
            text-align: center;
            color: #666;
            font-size: 12px;
        }
        .alert {
            background-color: #FEF2F2;
            border-left: 4px solid #EF4444;
            padding: 10px;
            margin: 10px 0;
        }
        .success {
            background-color: #F0FDF4;
            border-left: 4px solid #10B981;
            padding: 10px;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Sustainability Data Report</h1>
        <p><strong>{{ factory_name }}</strong></p>
        <p>{{ factory_location }}</p>
        <p>Period: {{ date_from }} to {{ date_to }}</p>
        <p>Generated: {{ generated_date }}</p>
    </div>

    <div class="section">
        <div class="section-title">Carbon Footprint Summary</div>
        <div class="metric-grid">
            <div class="metric-box">
                <div class="metric-label">Total Carbon Footprint</div>
                <div class="metric-value">{{ total_carbon_kg }} <span class="metric-unit">kg CO₂e</span></div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Carbon per Garment</div>
                <div class="metric-value">{{ carbon_per_garment_kg }} <span class="metric-unit">kg CO₂e</span></div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Total Garments Produced</div>
                <div class="metric-value">{{ total_garments }}</div>
            </div>
        </div>

        <h3>Emissions Breakdown</h3>
        <table class="breakdown-table">
            <tr>
                <th>Category</th>
                <th>Emissions (kg CO₂e)</th>
            </tr>
            <tr>
                <td>Materials (Fabric)</td>
                <td>{{ materials_emissions }}</td>
            </tr>
            <tr>
                <td>Energy (Electricity)</td>
                <td>{{ energy_emissions }}</td>
            </tr>
            <tr>
                <td>Water Treatment</td>
                <td>{{ water_emissions }}</td>
            </tr>
            <tr>
                <td>Chemicals & Dyes</td>
                <td>{{ chemicals_emissions }}</td>
            </tr>
            <tr>
                <td>Transportation</td>
                <td>{{ transport_emissions }}</td>
            </tr>
        </table>
    </div>

    <div class="section">
        <div class="section-title">Water & Energy Usage</div>
        <div class="metric-grid">
            <div class="metric-box">
                <div class="metric-label">Total Water Consumption</div>
                <div class="metric-value">{{ total_water_liters }} <span class="metric-unit">liters</span></div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Water per Garment</div>
                <div class="metric-value">{{ water_per_garment_liters }} <span class="metric-unit">liters</span></div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Total Electricity</div>
                <div class="metric-value">{{ total_electricity_kwh }} <span class="metric-unit">kWh</span></div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Electricity per Garment</div>
                <div class="metric-value">{{ electricity_per_garment_kwh }} <span class="metric-unit">kWh</span></div>
            </div>
        </div>
    </div>

    <div class="section">
        <div class="section-title">Chemical Compliance Status</div>
        {% if chemical_compliance_percentage >= 80 %}
        <div class="success">
            <strong>✓ Good Compliance:</strong> {{ compliant_chemicals }} out of {{ total_chemicals }} chemicals are REACH & ZDHC compliant ({{ chemical_compliance_percentage }}%)
        </div>
        {% else %}
        <div class="alert">
            <strong>⚠ Compliance Action Required:</strong> Only {{ compliant_chemicals }} out of {{ total_chemicals }} chemicals are REACH & ZDHC compliant ({{ chemical_compliance_percentage }}%)
        </div>
        {% endif %}

        {% if non_compliant_chemicals %}
        <div class="alert">
            <strong>Restricted Substances Detected:</strong>
            <ul>
                {% for chemical in non_compliant_chemicals %}
                <li>{{ chemical }}</li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}
    </div>

    <div class="section">
        <div class="section-title">Data Traceability & Audit Trail</div>
        <p>All data in this report is sourced from production records logged in the GreenThread platform. Every data entry and modification is tracked in an immutable audit log, ensuring full traceability and compliance readiness.</p>
        <p>This report can be shared with EU buyers to demonstrate compliance with CSRD requirements and Digital Product Passport regulations.</p>
    </div>

    <div class="footer">
        <p><strong>Data generated by GreenThread</strong> — Audit-ready, traceable sustainability data management</p>
        <p>www.greenthread.io | support@greenthread.io</p>
    </div>
</body>
</html>
        """

        template = Template(template_str)
        return template.render(**data)
