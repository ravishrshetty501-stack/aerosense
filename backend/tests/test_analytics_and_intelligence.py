import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_city_comparison_canonical_deduplication():
    """Verify that multi-city comparison canonicalizes and deduplicates duplicate requests via GET."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Request with duplicate city names via query parameters
        resp = await client.get("/api/v1/analytics/compare?cities=Tokyo&cities=London&cities=Tokyo&standard=US_EPA")
        assert resp.status_code == 200
        data = resp.json()
        assert "comparison" in data
        assert "standard" in data
        # Unique list of comparison items must have length 2 (Tokyo & London)
        returned_names = [c["city"] for c in data["comparison"]]
        assert len(returned_names) == 2
        assert "Tokyo" in returned_names
        assert "London" in returned_names

@pytest.mark.asyncio
async def test_system_network_status_structure():
    """Verify system telemetry network status returns honest provider states."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/system/network-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        providers = data["providers"]
        assert "waqi" in providers
        assert "open_meteo" in providers
        assert "gemini_ai" in providers
        # Validate that statuses belong to honest valid enum states
        valid_states = {"connected", "degraded", "unavailable", "not_configured"}
        assert providers["waqi"]["status"] in valid_states
        assert providers["open_meteo"]["status"] in valid_states
        assert providers["gemini_ai"]["status"] in valid_states

@pytest.mark.asyncio
async def test_verified_measurements_in_current_air_quality():
    """Verify current air quality returns verified pollutant observations with unit and attribution."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/air-quality/current?lat=35.68&lon=139.69&city=Tokyo")
        assert resp.status_code == 200
        data = resp.json()
        assert "measurements" in data
        assert "aqi_standard_results" in data
        measurements = data["measurements"]
        assert "pm25" in measurements
        pm25 = measurements["pm25"]
        assert "value" in pm25
        assert pm25["unit"] in ["ug/m3", "µg/m³"]
        assert "source" in pm25

