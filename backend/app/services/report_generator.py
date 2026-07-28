from sqlalchemy.orm import Session
from datetime import datetime
from jinja2 import Template
import logging
import os
from typing import Dict
from ..models import (
    BatchAllocation,
    Factory,
    Order,
    ProductionBatch,
    ProductionRecord,
)
from ..config import settings
from . import batch_carbon
from .carbon_calculator import CarbonCalculator

logger = logging.getLogger(__name__)

# WeasyPrint requires GTK runtime on Windows; deferred so the app starts
# even when WeasyPrint isn't installable on the dev machine. If unavailable,
# we save the rendered HTML alongside the PDF filename and skip PDF
# rendering — the rest of the flow (signing, anchoring, verify) is unaffected
# because those operate on the canonical JSON payload, not the PDF bytes.
try:  # pragma: no cover
    from weasyprint import HTML  # type: ignore
    _WEASYPRINT_OK = True
except Exception as _exc:  # pragma: no cover
    HTML = None  # type: ignore[assignment]
    _WEASYPRINT_OK = False
    logger.warning("WeasyPrint unavailable — PDF rendering disabled (%s)", _exc)


class ReportGenerator:
    """Service for generating PDF sustainability reports"""

    @staticmethod
    def batch_allocation_data(
        db: Session,
        factory_id: int,
        date_from: datetime,
        date_to: datetime,
    ) -> Dict:
        """Allocation Statement + data-quality mix for every order touched
        by a batch that started in the reporting window.

        This is the section buyers' auditors ask for: which ISO 14044 rung
        was used per batch, and what % of each footprint is MEASURED vs
        ESTIMATED vs DEFAULT_FACTOR. Also feeds the signed report payload —
        the statement is covered by the signature, not just the PDF.
        """
        order_ids = [
            row.order_id
            for row in (
                db.query(BatchAllocation.order_id)
                .join(ProductionBatch, ProductionBatch.id == BatchAllocation.batch_id)
                .filter(
                    ProductionBatch.factory_id == factory_id,
                    ProductionBatch.started_at >= date_from,
                    ProductionBatch.started_at <= date_to,
                )
                .distinct()
                .all()
            )
        ]
        orders = (
            db.query(Order).filter(Order.id.in_(order_ids)).order_by(Order.order_code).all()
            if order_ids else []
        )

        statements = []
        total_co2 = 0.0
        mix_weighted = {"measured": 0.0, "estimated": 0.0, "default_factor": 0.0}
        any_economic = False
        for order in orders:
            fp = batch_carbon.order_footprint(db, order)
            any_economic = any_economic or fp.used_economic_allocation
            total_co2 += fp.co2_kg
            for tier, pct in fp.quality_mix.items():
                mix_weighted[tier] += pct * fp.co2_kg
            statements.append({
                "order_id": order.id,
                "order_code": order.order_code,
                "buyer_name": order.buyer_name,
                "units": order.units,
                "co2_kg": fp.co2_kg,
                "water_l": fp.water_l,
                "quality_mix": fp.quality_mix,
                "used_economic_allocation": fp.used_economic_allocation,
                "batches": [
                    {
                        "batch_code": line.batch_code,
                        "process_type": line.process_type,
                        "allocation_method": line.allocation_method,
                        "allocated_share": line.allocated_share,
                        "co2_kg": line.co2_kg,
                        "is_rework": line.is_rework,
                        "outsourced": line.outsourced,
                        "data_quality_flags": line.data_quality_flags,
                        "allocation_note": line.allocation_note,
                    }
                    for line in fp.batch_lines
                ],
            })

        overall_mix = (
            {tier: round(v / total_co2, 2) for tier, v in mix_weighted.items()}
            if total_co2 > 0
            else {"measured": 0.0, "estimated": 0.0, "default_factor": 0.0}
        )

        return {
            "has_batch_data": bool(statements),
            "rework_rate": batch_carbon.rework_rate(db, factory_id),
            "order_statements": statements,
            "overall_quality_mix": overall_mix,
            "any_economic_allocation": any_economic,
        }

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
            # Numeric copy for template comparisons ({% if ... >= 80 %}) —
            # Jinja can't compare a formatted string against an int.
            "chemical_compliance_percentage_num": compliance_percentage,
            "total_chemicals": total_chemicals,
            "compliant_chemicals": compliant_chemicals,
            "non_compliant_chemicals": non_compliant_chemicals,
        }

        # Phase 2 sections: Allocation Statement, data-quality mix, rework
        # rate. Only rendered when the factory has batch-level data — legacy
        # per-record ("simple mode") reports are unchanged.
        report_data.update(
            ReportGenerator.batch_allocation_data(db, factory_id, date_from, date_to)
        )

        # Generate HTML from template
        html_content = ReportGenerator._get_html_template(report_data)

        # Generate PDF (or HTML fallback if WeasyPrint isn't installed).
        # Reports dir is configurable so dev can point it at a host path
        # like ./reports without needing the /app/reports Docker volume.
        reports_dir = settings.REPORTS_DIR
        os.makedirs(reports_dir, exist_ok=True)

        filename = f"sustainability_report_{factory_id}_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.pdf"
        filepath = os.path.join(reports_dir, filename)

        if _WEASYPRINT_OK and HTML is not None:
            HTML(string=html_content).write_pdf(filepath)
        else:
            # Dev fallback: WeasyPrint isn't installed (typical on Windows
            # without GTK). Save the rendered HTML next to where the PDF
            # would have lived so the report can still be inspected, signed,
            # and anchored. The signing/verify pipeline operates on canonical
            # JSON, not the PDF bytes, so it remains correct.
            html_filename = filename.replace(".pdf", ".html")
            html_filepath = os.path.join(reports_dir, html_filename)
            with open(html_filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(
                "WeasyPrint unavailable — saved HTML to %s instead of PDF",
                html_filepath,
            )
            # Return the .pdf filename so DB references stay stable; the
            # download endpoint can fall back to the .html sibling.
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
        {% if chemical_compliance_percentage_num >= 80 %}
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

    {% if has_batch_data %}
    <div class="section">
        <div class="section-title">Batch Production & Rework</div>
        <div class="metric-grid">
            <div class="metric-box">
                <div class="metric-label">Rework Rate (rework batches ÷ total)</div>
                <div class="metric-value">{{ "%.1f"|format(rework_rate * 100) }} <span class="metric-unit">%</span></div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Overall Data Quality (share of footprint)</div>
                <div class="metric-value" style="font-size: 16px;">
                    {{ overall_quality_mix.measured }}% measured ·
                    {{ overall_quality_mix.estimated }}% estimated ·
                    {{ overall_quality_mix.default_factor }}% default factors
                </div>
            </div>
        </div>
        <p style="font-size: 12px; color: #666;">
            Rework runs (re-dyeing, re-processing) are recorded as separate batches and their
            consumption is added to the affected orders — footprints reflect what actually happened.
        </p>
    </div>

    <div class="section">
        <div class="section-title">Allocation Statement</div>
        <p style="font-size: 12px; color: #666;">
            Shared production batches are split across orders following the ISO 14044 hierarchy
            (subdivision first, then physical/mass allocation; unit or economic allocation only where
            noted). Shares are fixed at allocation time and preserved in the audit trail.
        </p>
        {% if any_economic_allocation %}
        <div class="alert">
            <strong>⚠ Economic allocation used:</strong> at least one batch in this period was
            allocated by order value rather than mass. See the per-batch method column below.
        </div>
        {% endif %}
        {% for stmt in order_statements %}
        <h3 style="margin-bottom: 4px;">Order {{ stmt.order_code }}{% if stmt.buyer_name %} — {{ stmt.buyer_name }}{% endif %}</h3>
        <p style="font-size: 12px; margin-top: 0;">
            {{ stmt.units }} units · {{ "%.1f"|format(stmt.co2_kg) }} kg CO₂e ·
            {{ "%.0f"|format(stmt.water_l) }} L water ·
            data quality: {{ stmt.quality_mix.measured }}% measured,
            {{ stmt.quality_mix.estimated }}% estimated,
            {{ stmt.quality_mix.default_factor }}% default factors
        </p>
        <table class="breakdown-table">
            <tr>
                <th>Batch</th>
                <th>Process</th>
                <th>Method</th>
                <th>Share</th>
                <th>kg CO₂e</th>
                <th>Notes</th>
            </tr>
            {% for b in stmt.batches %}
            <tr>
                <td>{{ b.batch_code }}</td>
                <td>{{ b.process_type }}</td>
                <td>{{ b.allocation_method }}</td>
                <td>{{ "%.1f"|format(b.allocated_share * 100) }}%</td>
                <td>{{ "%.2f"|format(b.co2_kg) }}</td>
                <td>
                    {%- if b.is_rework %}rework {% endif -%}
                    {%- if b.outsourced %}outsourced {% endif -%}
                    {%- if "default_factors" in b.data_quality_flags %}default factors {% endif -%}
                    {%- if b.allocation_note %}{{ b.allocation_note }}{% endif -%}
                </td>
            </tr>
            {% endfor %}
        </table>
        {% endfor %}
    </div>
    {% endif %}

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
