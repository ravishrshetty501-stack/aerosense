import io
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.services.providers.manager import data_manager

class ReportService:
    """
    Environmental report generator.
    Produces comprehensive daily and weekly environmental intelligence reports
    in both structured JSON and professional PDF format.
    """

    async def generate_report_data(
        self,
        lat: float,
        lon: float,
        city_name: str,
        period: str = "Daily Summary",
        standard: str = "US_EPA"
    ) -> Dict[str, Any]:
        res = await data_manager.get_unified_air_quality(lat, lon, city_name, standard)
        aqi_info = res.aqi_standard_results.get(standard, res.aqi_standard_results.get("US_EPA"))
        
        meas_summary = {}
        for k, v in res.measurements.items():
            meas_summary[k] = {
                "value": v.value,
                "unit": v.unit,
                "type": v.measurement_type,
                "source": v.source,
                "timestamp": v.observation_timestamp.isoformat()
            }
            
        report_data = {
            "title": f"AeroSense AI — Environmental Intelligence Report: {city_name}",
            "city": city_name,
            "period": period,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "aqi_standard": standard,
            "aqi_value": aqi_info.get("aqi"),
            "aqi_category": aqi_info.get("category"),
            "dominant_pollutant": res.dominant_pollutant,
            "primary_source": res.primary_source,
            "is_ground_observation": res.is_ground_observation,
            "measurements": meas_summary,
            "health_advisory": aqi_info.get("advisory"),
            "forecast_summary": f"Next 24h expected conditions based on atmospheric transport models."
        }
        return report_data

    def generate_pdf(self, report_data: Dict[str, Any]) -> bytes:
        """Generates a professional PDF document from environmental report data."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor('#0b1329')
        )
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor('#475569')
        )
        h2_style = ParagraphStyle(
            'ReportH2',
            parent=styles['Heading2'],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#0f1b38'),
            spaceBefore=12,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'ReportBody',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#1e293b')
        )

        # Header
        story.append(Paragraph("AEROSENSE AI | GLOBAL AIR QUALITY REPORT", ParagraphStyle('HeaderBadge', fontSize=9, textColor=colors.HexColor('#0284c7'), spaceAfter=4)))
        story.append(Paragraph(f"Environmental Intelligence Briefing: {report_data['city']}", title_style))
        story.append(Paragraph(f"Period: {report_data['period']} | Generated: {report_data['generated_at']}", subtitle_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284c7'), spaceAfter=15))

        # Executive Summary Box
        summary_data = [
            [
                Paragraph("<b>Overall AQI</b>", subtitle_style),
                Paragraph("<b>Category</b>", subtitle_style),
                Paragraph("<b>Dominant Pollutant</b>", subtitle_style),
                Paragraph("<b>Data Source</b>", subtitle_style)
            ],
            [
                Paragraph(f"<font size=18 color='#0284c7'><b>{report_data.get('aqi_value', 'N/A')}</b></font>", body_style),
                Paragraph(f"<b>{report_data.get('aqi_category', 'N/A')}</b>", body_style),
                Paragraph(f"<b>{report_data.get('dominant_pollutant', 'N/A')}</b>", body_style),
                Paragraph(f"{'Physical Ground Sensor' if report_data.get('is_ground_observation') else 'Atmospheric Model'}", body_style)
            ]
        ]
        summary_table = Table(summary_data, colWidths=[100, 140, 120, 180])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f5f9')),
            ('PADDING', (0,0), (-1,-1), 8),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 15))

        # Measurements Table
        story.append(Paragraph("Verified Pollutant Concentrations", h2_style))
        meas_rows = [
            ["Pollutant", "Observed Value", "Unit", "Measurement Type", "Provider Attribution"]
        ]
        for p, d in report_data.get("measurements", {}).items():
            meas_rows.append([
                p.upper(),
                str(d.get("value", "N/A")),
                d.get("unit", "ug/m3"),
                d.get("type", "model_estimate"),
                d.get("source", "Open-Meteo")[:35]
            ])
            
        meas_table = Table(meas_rows, colWidths=[80, 90, 70, 120, 180])
        meas_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f1b38')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('PADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(meas_table)
        story.append(Spacer(1, 15))

        # Health Advisory
        story.append(Paragraph("Health & Activity Advisory", h2_style))
        story.append(Paragraph(report_data.get("health_advisory", "Air quality is within normal parameters."), body_style))
        story.append(Spacer(1, 10))

        # Disclaimer
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceAfter=10))
        disclaimer = (
            "<i>Attribution Notice: Real-time environmental readings are ingested from OpenAQ API v3 and Open-Meteo Air Quality APIs. "
            "Calculations comply with US EPA, India CPCB, and EEA standards. This report provides ambient environmental metrics and general public health guidance; "
            "it is not intended as personalized medical diagnosis.</i>"
        )
        story.append(Paragraph(disclaimer, ParagraphStyle('Disclaimer', fontSize=8, leading=11, textColor=colors.HexColor('#64748b'))))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

report_service = ReportService()
