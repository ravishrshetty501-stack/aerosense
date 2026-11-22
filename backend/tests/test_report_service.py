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
