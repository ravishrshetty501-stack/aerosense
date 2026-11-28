import io
import json
import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from xml.sax.saxutils import escape as xml_escape
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.services.providers.manager import data_manager
from app.services.aqi.engine import normalize_standard_name


def _is_finite_number(value: Any) -> bool:
    """Returns True only for finite int/float values (excluding bool, None, NaN, and +/-inf)."""
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError, TypeError):
        return False


def _format_pdf_number(value: Any, fallback: str = "N/A") -> str:
    """Formats a finite numeric value (preserving genuine 0) or returns fallback."""
    if not _is_finite_number(value):
        return fallback
    normalized = 0 if value == 0 and isinstance(value, int) else (0.0 if value == 0 else value)
    return str(normalized)


def _resolve_pdf_data_source(report_data: Dict[str, Any]) -> str:
    """
    Determines PDF data-source attribution from verified finite measurement metadata.
    Never infers 'Atmospheric Model' from empty telemetry or bare is_ground_observation=False.
    """
    measurements = report_data.get("measurements")
    if not isinstance(measurements, dict) or not measurements:
        return "Unavailable"

    valid_entries = [
        entry
        for entry in measurements.values()
        if isinstance(entry, dict) and _is_finite_number(entry.get("value"))
    ]
    if not valid_entries:
        return "Unavailable"

    has_ground_meta = False
    has_model_meta = False
    has_other_attributed_meta = False

    for entry in valid_entries:
        m_type = str(entry.get("type") or "").strip().lower()
        m_source = str(entry.get("source") or "").strip()
        if m_type == "ground_observation":
            has_ground_meta = True
        elif m_type in {"model_estimate", "forecast", "historical", "ground_anchored_reanalysis", "model"}:
            has_model_meta = True
        elif (
            (m_type and m_type not in {"unavailable", "unknown", "none", "n/a"})
            or (m_source and m_source.lower() not in {"unavailable", "unknown", "none", "n/a"})
        ):
            has_other_attributed_meta = True

    if has_ground_meta or (report_data.get("is_ground_observation") is True and (has_model_meta or has_other_attributed_meta)):
        return "Physical Ground Sensor"
    if has_model_meta or has_other_attributed_meta:
        return "Atmospheric Model"
    return "Unavailable"


def _escape_pdf_text(value: Any, fallback: str = "N/A") -> str:
    """Escapes dynamic user/provider strings for safe insertion into ReportLab XML Paragraphs."""
    text = fallback if value is None else str(value)
    return xml_escape(text, entities={'"': "&quot;", "'": "&apos;"})


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
        canonical_standard = normalize_standard_name(standard)
        res = await data_manager.get_unified_air_quality(lat, lon, city_name, canonical_standard)
        aqi_info = (
            res.aqi_standard_results.get(canonical_standard)
            or res.aqi_standard_results.get("US_EPA")
            or {}
        )

        meas_summary = {}
        for k, v in (res.measurements or {}).items():
            meas_summary[k] = {
                "value": v.value if _is_finite_number(v.value) else None,
                "unit": v.unit,
                "type": v.measurement_type,
                "source": v.source,
                "timestamp": v.observation_timestamp.isoformat() if v.observation_timestamp else None,
            }

        report_data = {
            "title": f"AeroSense AI — Environmental Intelligence Report: {city_name}",
            "city": city_name,
            "period": period,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "aqi_standard": canonical_standard,
            "aqi_value": aqi_info.get("aqi") if _is_finite_number(aqi_info.get("aqi")) else None,
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
        safe_city = _escape_pdf_text(report_data.get("city"), "Location")
        safe_period = _escape_pdf_text(report_data.get("period"), "Daily Summary")
        safe_generated_at = _escape_pdf_text(report_data.get("generated_at"), "N/A")
        safe_aqi = _escape_pdf_text(_format_pdf_number(report_data.get("aqi_value"), fallback="N/A"), "N/A")
        safe_category = _escape_pdf_text(report_data.get("aqi_category") or "Unavailable", "Unavailable")
        safe_dominant = _escape_pdf_text(report_data.get("dominant_pollutant") or "Unavailable", "Unavailable")
        safe_data_source = _escape_pdf_text(_resolve_pdf_data_source(report_data), "Unavailable")
        safe_advisory = _escape_pdf_text(
            report_data.get("health_advisory"),
            "Air quality health advisory is currently unavailable.",
        )

        story.append(Paragraph("AEROSENSE AI | GLOBAL AIR QUALITY REPORT", ParagraphStyle('HeaderBadge', fontSize=9, textColor=colors.HexColor('#0284c7'), spaceAfter=4)))
        story.append(Paragraph(f"Environmental Intelligence Briefing: {safe_city}", title_style))
        story.append(Paragraph(f"Period: {safe_period} | Generated: {safe_generated_at}", subtitle_style))
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
                Paragraph(f"<font size=18 color='#0284c7'><b>{safe_aqi}</b></font>", body_style),
                Paragraph(f"<b>{safe_category}</b>", body_style),
                Paragraph(f"<b>{safe_dominant}</b>", body_style),
                Paragraph(safe_data_source, body_style)
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
        measurements = report_data.get("measurements")
        if isinstance(measurements, dict) and measurements:
            for p, d in measurements.items():
                entry = d if isinstance(d, dict) else {}
                val_str = _format_pdf_number(entry.get("value"), fallback="Unavailable")
                unit_str = str(entry.get("unit") or "N/A")
                type_str = str(entry.get("type") or "unavailable")
                source_raw = entry.get("source")
                source_str = str(source_raw).strip()[:35] if source_raw else "Unavailable"
                if not source_str:
                    source_str = "Unavailable"
                meas_rows.append([
                    str(p).upper(),
                    val_str,
                    unit_str,
                    type_str,
                    source_str,
                ])
        else:
            meas_rows.append(["N/A", "Unavailable", "—", "unavailable", "No valid telemetry available"])
            
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
        story.append(Paragraph(safe_advisory, body_style))
        story.append(Spacer(1, 10))

        # Disclaimer
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceAfter=10))
        disclaimer = (
            "<i>Attribution Notice: Real-time environmental observations are ingested from the WAQI Ground Station Network "
            "and Copernicus / Open-Meteo Atmospheric Models. Calculations comply with US EPA, India CPCB, and EEA standards. "
            "This report provides ambient environmental metrics and general public health guidance; it is not intended as personalized medical diagnosis.</i>"
        )
        story.append(Paragraph(disclaimer, ParagraphStyle('Disclaimer', fontSize=8, leading=11, textColor=colors.HexColor('#64748b'))))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

report_service = ReportService()
