import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from app.main import app
from app.core.security import create_access_token
from app.services.aqi.engine import aqi_engine
from app.services.ai_service import ai_service
from app.services.providers.manager import data_manager

@pytest.mark.asyncio
async def test_protected_routes_unauthorized_rejection():
    """Verify that protected alert and user routes strictly reject unauthenticated requests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Missing Authorization header
        res1 = await ac.get("/api/v1/alerts/rules")
        assert res1.status_code == 401

        # Malformed Authorization header
        res2 = await ac.get("/api/v1/alerts/rules", headers={"Authorization": "InvalidBearer token123"})
        assert res2.status_code == 401

        # Forged / Tampered token
        res3 = await ac.get("/api/v1/alerts/rules", headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake.signature"})
        assert res3.status_code == 401

        # Expired token (delta = -100 seconds)
        expired_token = create_access_token("test-user-id", expires_delta=-100)
        res4 = await ac.get("/api/v1/alerts/rules", headers={"Authorization": f"Bearer {expired_token}"})
        assert res4.status_code == 401

@pytest.mark.asyncio
async def test_empty_and_whitespace_location_search():
    """Verify that empty, blank, or special character queries do not crash the geocoding service."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/locations/search?q=%20%20%20")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) == 0

def test_aqi_engine_extreme_and_outlier_inputs():
    """Verify AQI engine behaves deterministically with zero, negative, and extreme outlier inputs."""
    # Negative values should be gracefully clamped to 0
    res_neg = aqi_engine.calculate({"pm25": -15.0}, standard="US_EPA")
    assert res_neg["aqi"] == 0
    assert res_neg["category"] == "Good"

    # Zero concentrations
    res_zero = aqi_engine.calculate({"pm25": 0.0, "pm10": 0.0}, standard="US_EPA")
    assert res_zero["aqi"] == 0
    assert res_zero["category"] == "Good"

    # Extreme apocalyptic particulate level (1500 ug/m3 PM2.5) -> must cap at Hazardous (500 AQI)
    res_extreme = aqi_engine.calculate({"pm25": 1500.0}, standard="US_EPA")
    assert res_extreme["aqi"] == 500
    assert res_extreme["category"] == "Hazardous"

@pytest.mark.asyncio
async def test_gemini_api_quota_failure_resilience():
    """Verify that when Gemini API throws 429 Quota Exceeded, AI service falls back gracefully."""
    with patch("httpx.AsyncClient.post", side_effect=Exception("429 Resource has been exhausted (e.g. check quota)")):
        result = await ai_service.chat(
            user_message="Is it safe to run outside in Tokyo today?",
            location_hint="Tokyo"
        )
        assert "response" in result
        assert len(result["response"]) > 20
        # Fallback response must provide safe guidance without crashing
        assert "Tokyo" in result["response"] or "air quality" in result["response"].lower()

@pytest.mark.asyncio
async def test_waqi_provider_failure_resilience():
    """Verify that when WAQI API fails with 503, unified data manager falls back to Open-Meteo."""
    with patch("app.services.providers.waqi.waqi_provider.get_current_air_quality", return_value=None):
        result = await data_manager.get_unified_air_quality(
            lat=35.6895,
            lon=139.6917,
            city_name="Tokyo",
            preferred_standard="US_EPA"
        )
        # Result must still succeed using Open-Meteo model data
        assert result.location.city == "Tokyo"
        assert result.aqi_standard_results["US_EPA"]["aqi"] is not None
        assert result.dominant_pollutant is not None
        assert result.is_ground_observation is False
