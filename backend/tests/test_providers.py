import pytest
from app.services.providers.open_meteo import open_meteo_provider
from app.services.providers.manager import data_manager

@pytest.mark.asyncio
async def test_open_meteo_geocoding():
    results = await open_meteo_provider.search_locations("Tokyo", limit=3)
    assert len(results) > 0
    assert "Tokyo" in results[0]["name"]
    assert "latitude" in results[0]
    assert "longitude" in results[0]

@pytest.mark.asyncio
async def test_open_meteo_air_quality():
    # Coordinates for Paris (lat: 48.8566, lon: 2.3522)
    data = await open_meteo_provider.get_current_air_quality(48.8566, 2.3522, "Paris")
    assert data is not None
    assert "measurements" in data
    assert "pm25" in data["measurements"]
    pm25 = data["measurements"]["pm25"]
    assert pm25.pollutant == "pm25"
    assert pm25.unit in ["ug/m3", "μg/m³"]
    assert pm25.measurement_type == "model_estimate"
    assert pm25.observation_timestamp is not None

@pytest.mark.asyncio
async def test_unified_data_manager():
    # Test unified manager with multi-standard calculation
    resp = await data_manager.get_unified_air_quality(51.5074, -0.1278, "London", "US_EPA")
    assert resp.location.name == "London"
    assert "US_EPA" in resp.aqi_standard_results
    assert "INDIA_CPCB" in resp.aqi_standard_results
    assert "EUROPEAN_AQI" in resp.aqi_standard_results
    assert len(resp.measurements) > 0
    assert resp.primary_source is not None
    assert resp.data_freshness_minutes >= 1
