import pytest
from app.services.report_service import ReportService, report_service

@pytest.mark.asyncio
async def test_generate_report_data_success():
    """Verifies that generate_report_data retrieves real atmospheric data and structures the report."""
    data = await report_service.generate_report_data(
        lat=35.6895,
        lon=139.6917,
        city_name="Tokyo",
        period="Daily Summary",
        standard="US_EPA"
    )
    assert data["city"] == "Tokyo"
    assert data["period"] == "Daily Summary"
    assert data["aqi_standard"] == "US_EPA"
    assert "generated_at" in data
    assert "aqi_value" in data
    assert "aqi_category" in data
    assert "dominant_pollutant" in data
    assert "measurements" in data
    assert isinstance(data["measurements"], dict)
    assert "health_advisory" in data

@pytest.mark.asyncio
async def test_generate_report_data_alternative_standard():
    """Verifies report generation with Indian CPCB and European AQI standards."""
    data_in = await report_service.generate_report_data(
        lat=28.6139,
        lon=77.2090,
        city_name="Delhi",
        period="Weekly Assessment",
        standard="INDIA_CPCB"
    )
    assert data_in["city"] == "Delhi"
    assert data_in["period"] == "Weekly Assessment"
    assert data_in["aqi_standard"] == "INDIA_CPCB"

@pytest.mark.asyncio
async def test_generate_pdf_valid_document():
    """Verifies ReportLab PDF generation outputs valid PDF bytes with header signature."""
    service = ReportService()
    mock_data = {
        "title": "AeroSense AI — Environmental Intelligence Report: Paris",
        "city": "Paris",
        "period": "Daily Summary",
        "generated_at": "2026-11-22 12:00 UTC",
        "aqi_standard": "US_EPA",
        "aqi_value": 45,
        "aqi_category": "Good",
        "dominant_pollutant": "pm25",
        "primary_source": "WAQI Ground Station Network",
        "is_ground_observation": True,
        "measurements": {
            "pm25": {"value": 10.5, "unit": "ug/m3", "type": "ground_observation", "source": "WAQI Paris Centre", "timestamp": "2026-11-22T11:00:00Z"},
            "pm10": {"value": 18.2, "unit": "ug/m3", "type": "ground_observation", "source": "WAQI Paris Centre", "timestamp": "2026-11-22T11:00:00Z"},
            "no2": {"value": 22.1, "unit": "ug/m3", "type": "model_estimate", "source": "Copernicus CAMS", "timestamp": "2026-11-22T11:00:00Z"},
        },
        "health_advisory": "Air quality is satisfactory and poses little or no risk to public health.",
        "forecast_summary": "Next 24h expected conditions remain stable."
    }

    pdf_bytes = service.generate_pdf(mock_data)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000

def test_generate_pdf_edge_cases_empty_measurements():
    """Verifies PDF generation is resilient to missing pollutant measurements and N/A values."""
    service = ReportService()
    minimal_data = {
        "title": "AeroSense AI — Environmental Intelligence Report: Remote Island",
        "city": "Remote Island",
        "period": "Emergency Bulletin",
        "generated_at": "2026-11-22 12:00 UTC",
        "aqi_standard": "US_EPA",
        "aqi_value": None,
        "aqi_category": "Unknown",
        "dominant_pollutant": "N/A",
        "primary_source": "None",
        "is_ground_observation": False,
        "measurements": {},
        "health_advisory": "No ground telemetry detected; atmospheric models indicate baseline clean air.",
    }

    pdf_bytes = service.generate_pdf(minimal_data)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_generate_pdf_escapes_xml_markup_and_unicode():
    """ReportLab generation must escape &, <, >, quotes in dynamic text while preserving valid PDF output."""
    service = ReportService()
    adversarial_data = {
        "title": "AeroSense AI — Report",
        "city": 'AT&T <script>alert(1)</script> "Seoul" & 東京',
        "period": 'Daily & <font color="red">Weekly</font> Summary\'s',
        "generated_at": "2026-11-27 12:00 UTC <now>",
        "aqi_standard": "US_EPA",
        "aqi_value": 0,
        "aqi_category": "Good & <Safe>",
        "dominant_pollutant": "PM2.5 <10>",
        "primary_source": "WAQI & Copernicus",
        "is_ground_observation": True,
        "measurements": {
            "pm25": {"value": 0.0, "unit": "µg/m³", "type": "ground_observation", "source": "Station <A> & B"}
        },
        "health_advisory": 'Keep exposure < 35 µg/m³ & avoid <b>unclosed tags "forever".',
    }

    pdf_bytes = service.generate_pdf(adversarial_data)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_build_pdf_content_disposition_sanitization():
    """Content-Disposition enforces safe ASCII fallback filenames and RFC 5987 UTF-8 filenames."""
    from urllib.parse import unquote
    from app.api.v1.reports import build_pdf_content_disposition

    # Ordinary ASCII values
    ordinary = build_pdf_content_disposition("New York", "Daily Summary")
    assert ordinary == 'attachment; filename="AeroSense_New_York_Daily_Summary.pdf"'

    # Empty values fall back safely
    empty = build_pdf_content_disposition("", "   ")
    assert empty == 'attachment; filename="AeroSense_Location_Report.pdf"'

    # Quotes, semicolons, CR/LF, control chars, path separators, traversal sequences
    malicious = build_pdf_content_disposition(
        '../../etc/passwd"\r\n\x00;evil=1',
        'Daily\\../Period";bad\n',
    )
    assert "\r" not in malicious
    assert "\n" not in malicious
    assert "\x00" not in malicious
    assert ".." not in malicious
    assert "/" not in malicious
    assert "\\" not in malicious
    assert malicious.count('"') == 2  # Only outer filename="..." quotes
    assert malicious.startswith('attachment; filename="AeroSense_')
    assert malicious.endswith('.pdf"')

    # Very long input is length-bounded
    long_header = build_pdf_content_disposition("A" * 200, "B" * 200)
    assert len(long_header) < 160

    # Non-Latin-1 / Unicode city name emits valid ASCII fallback + RFC 5987 filename*
    unicode_header = build_pdf_content_disposition("東京 & São Paulo", "Daily Summary")
    unicode_header.encode("latin-1")  # Must be strict HTTP header latin-1 safe
    assert 'filename="AeroSense_' in unicode_header
    assert "filename*=UTF-8''" in unicode_header
    utf8_part = unicode_header.split("filename*=UTF-8''", 1)[1]
    assert "東京" in unquote(utf8_part)
    assert "São_Paulo" in unquote(utf8_part)


@pytest.mark.asyncio
async def test_export_pdf_endpoint_asgi_filename_and_markup_safety(monkeypatch):
    """ASGI integration test verifying /reports/export/pdf handles Unicode & adversarial period inputs without HTTP 500."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.services.providers.manager import data_manager

    async def fake_search_cities(_city: str):
        return [{"name": 'São Paulo <test> 東京', "latitude": -23.5505, "longitude": -46.6333}]

    async def fake_generate_report_data(lat, lon, city_name, period, standard):
        return {
            "city": city_name,
            "period": period,
            "generated_at": "2026-11-27 12:00 UTC",
            "aqi_value": 42,
            "aqi_category": "Good",
            "dominant_pollutant": "pm25",
            "is_ground_observation": False,
            "measurements": {},
            "health_advisory": "Safe conditions <all day> & clear air.",
        }

    monkeypatch.setattr(data_manager, "search_cities", fake_search_cities)
    monkeypatch.setattr(report_service, "generate_report_data", fake_generate_report_data)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/reports/export/pdf",
            params={
                "city": "Sao Paulo",
                "period": 'Daily";\r\n/..\\<script>alert(1)</script>',
                "standard": "US_EPA",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content.startswith(b"%PDF")
        cd = resp.headers["content-disposition"]
        cd.encode("latin-1")
        assert "\r" not in cd and "\n" not in cd
        assert "filename*=UTF-8''" in cd


def test_generate_pdf_missing_null_nonfinite_and_zero_resilience(monkeypatch):
    """
    Verify PDF generation handles empty/None/NaN/inf fields without crashing, preserves genuine 0,
    never prints literal 'None', and displays 'Unavailable' when no valid measurements exist.
    """
    from app.services import report_service as rs_mod
    from app.services.report_service import _format_pdf_number, _resolve_pdf_data_source

    service = ReportService()

    captured_tables = []
    orig_table = rs_mod.Table

    def spy_table(data, *args, **kwargs):
        captured_tables.append(data)
        return orig_table(data, *args, **kwargs)

    monkeypatch.setattr(rs_mod, "Table", spy_table)

    # 1. Empty measurements & is_ground_observation=False -> summary source must be 'Unavailable'
    empty_report = {
        "city": "Atlantis",
        "period": "Daily Summary",
        "generated_at": "2026-11-27 12:00 UTC",
        "aqi_value": None,
        "aqi_category": None,
        "dominant_pollutant": None,
        "primary_source": None,
        "is_ground_observation": False,
        "measurements": {},
        "health_advisory": None,
    }
    assert _resolve_pdf_data_source(empty_report) == "Unavailable"
    empty_pdf = service.generate_pdf(empty_report)
    assert empty_pdf.startswith(b"%PDF")
    assert captured_tables[0][1][3].text == "Unavailable"
    assert captured_tables[0][1][0].text == "<font size=18 color='#0284c7'><b>N/A</b></font>"
    assert captured_tables[1][1] == ["N/A", "Unavailable", "—", "unavailable", "No valid telemetry available"]

    captured_tables.clear()

    # 2. Explicit source=None, value=None, NaN, infinities, and measurements with only non-finite values
    nonfinite_report = {
        "city": "Edgeville",
        "period": "Daily Summary",
        "generated_at": "2026-11-27 12:00 UTC",
        "aqi_value": float("nan"),
        "aqi_category": "",
        "dominant_pollutant": "",
        "is_ground_observation": False,
        "measurements": {
            "pm25": {"value": None, "unit": "ug/m3", "type": "unavailable", "source": None},
            "pm10": {"value": float("inf"), "unit": "ug/m3", "type": "model_estimate", "source": None},
            "no2": {"value": float("-inf"), "unit": "ug/m3", "type": "model_estimate", "source": "Test"},
        },
        "health_advisory": "",
    }
    assert _resolve_pdf_data_source(nonfinite_report) == "Unavailable"
    assert _format_pdf_number(float("nan")) == "N/A"
    assert _format_pdf_number(float("inf")) == "N/A"
    nonfinite_pdf = service.generate_pdf(nonfinite_report)
    assert nonfinite_pdf.startswith(b"%PDF")
    assert captured_tables[0][1][3].text == "Unavailable"
    for row in captured_tables[1][1:]:
        assert row[1] == "Unavailable"
        assert "None" not in row

    captured_tables.clear()

    # 3. Genuine 0 values with valid ground_observation metadata and model_estimate metadata
    ground_zero_report = {
        "city": "Reykjavik",
        "period": "Daily Summary",
        "generated_at": "2026-11-27 12:00 UTC",
        "aqi_value": 0,
        "aqi_category": "Good",
        "dominant_pollutant": "PM25",
        "is_ground_observation": True,
        "measurements": {
            "pm25": {"value": 0, "unit": "ug/m3", "type": "ground_observation", "source": "Station Alpha"},
        },
        "health_advisory": "Clean.",
    }
    assert _resolve_pdf_data_source(ground_zero_report) == "Physical Ground Sensor"
    ground_pdf = service.generate_pdf(ground_zero_report)
    assert ground_pdf.startswith(b"%PDF")
    assert "<b>0</b>" in captured_tables[0][1][0].text
    assert captured_tables[0][1][3].text == "Physical Ground Sensor"
    assert captured_tables[1][1][:2] == ["PM25", "0"]

    model_valid_report = {
        "city": "Zurich",
        "period": "Daily Summary",
        "generated_at": "2026-11-27 12:00 UTC",
        "aqi_value": 18,
        "aqi_category": "Good",
        "dominant_pollutant": "NO2",
        "is_ground_observation": False,
        "measurements": {
            "no2": {"value": 14.2, "unit": "ug/m3", "type": "model_estimate", "source": "Open-Meteo CAMS"},
        },
        "health_advisory": "Clean.",
    }
    assert _resolve_pdf_data_source(model_valid_report) == "Atmospheric Model"
    model_pdf = service.generate_pdf(model_valid_report)
    assert model_pdf.startswith(b"%PDF")
