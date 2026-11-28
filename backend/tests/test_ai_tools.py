import pytest
from unittest.mock import AsyncMock, patch
from app.services.ai_service import ai_service
from app.services.providers.base import AirQualityResponse, LocationInfo

@pytest.mark.asyncio
async def test_tool_get_air_quality():
    res = await ai_service.execute_tool("get_air_quality", {"location": "London", "standard": "US_EPA"})
    assert "error" not in res
    assert res["city"] == "London"
    assert "aqi_summary" in res
    assert "measurements" in res
    assert res["aqi_summary"]["aqi"] is not None

@pytest.mark.asyncio
async def test_tool_compare_locations():
    res = await ai_service.execute_tool("compare_locations", {"locations": ["Tokyo", "Paris"], "standard": "US_EPA"})
    assert "cities" in res
    assert len(res["cities"]) == 2
    cities = [c["city"] for c in res["cities"]]
    assert "Tokyo" in cities
    assert "Paris" in cities

@pytest.mark.asyncio
async def test_tool_get_health_guidance():
    res = await ai_service.execute_tool("get_health_guidance", {"location": "New York", "activity": "running"})
    assert "safety_assessment" in res
    assert "official_advisory" in res
    assert res["activity"] == "running"

@pytest.mark.asyncio
async def test_tool_get_pollution_history():
    res = await ai_service.execute_tool("get_pollution_history", {"location": "Berlin"})
    assert "error" not in res
    assert res["city"] == "Berlin"
    assert "hourly_history_sample" in res
    assert isinstance(res["hourly_history_sample"], list)

@pytest.mark.asyncio
async def test_tool_get_forecast():
    res = await ai_service.execute_tool("get_forecast", {"location": "Madrid"})
    assert "error" not in res
    assert res["city"] == "Madrid"
    assert "forecast_sample" in res
    assert isinstance(res["forecast_sample"], list)

@pytest.mark.asyncio
async def test_tool_get_station_details():
    res = await ai_service.execute_tool("get_station_details", {"location": "Tokyo"})
    assert "error" not in res
    assert res["city"] == "Tokyo"
    assert "stations_found" in res
    assert "nearby_stations" in res
    assert isinstance(res["nearby_stations"], list)

@pytest.mark.asyncio
async def test_tool_get_pollution_trends():
    res = await ai_service.execute_tool("get_pollution_trends", {"location": "Delhi", "pollutant": "pm25"})
    assert "error" not in res
    assert res["city"] == "Delhi"
    assert res["pollutant"] == "pm25"
    assert "current" in res
    assert "trend_trajectory" in res
    assert "spike_detected" in res

@pytest.mark.asyncio
async def test_tool_create_environmental_report():
    res = await ai_service.execute_tool("create_environmental_report", {"location": "London", "standard": "US_EPA"})
    assert "error" not in res
    assert res["city"] == "London"
    assert "report_id" in res
    assert res["report_id"].startswith("REP-")
    assert "recommended_actions" in res
    assert len(res["recommended_actions"]) >= 1

@pytest.mark.asyncio
async def test_tool_unknown_and_invalid_city():
    # Unknown tool
    unknown_res = await ai_service.execute_tool("nonexistent_tool", {})
    assert "error" in unknown_res
    assert "Unknown tool" in unknown_res["error"]

    # City not found
    bad_city_res = await ai_service.execute_tool("get_air_quality", {"location": "ZZZZNonExistentCity999"})
    assert "error" in bad_city_res

@pytest.mark.asyncio
async def test_ai_chat_grounded_response():
    resp = await ai_service.chat("What is the current air quality in Tokyo and is it safe to run?")
    assert "response" in resp
    assert len(resp["response"]) > 50
    assert "Tokyo" in resp["response"]


def _make_mock_aq_response(us_epa_result: dict) -> AirQualityResponse:
    return AirQualityResponse(
        location=LocationInfo(name="TestCity", city="TestCity", latitude=35.0, longitude=139.0),
        measurements={},
        aqi_standard_results={"US_EPA": us_epa_result},
        dominant_pollutant=None,
        hourly_history=[],
        forecast=[],
        primary_source="Test Provider",
        data_freshness_minutes=5,
        is_ground_observation=False,
    )


@pytest.mark.asyncio
async def test_tool_get_health_guidance_aqi_edge_cases():
    """Verify get_health_guidance handles None/missing/non-finite AQI safely and preserves 0 and all valid bands."""
    mock_city = [{"name": "TestCity", "latitude": 35.0, "longitude": 139.0}]

    unavailable_cases = [
        {"aqi": None, "category": "Good", "advisory": None},
        {},  # Missing aqi key
        {"aqi": float("nan"), "category": "Moderate"},
        {"aqi": float("inf"), "category": "Severe"},
        {"aqi": float("-inf"), "category": "Good"},
        {"aqi": 10**400, "category": "Hazardous"},
        {"aqi": -10**400, "category": "Good"},
        {"aqi": True, "category": "Good"},
    ]

    for us_epa_payload in unavailable_cases:
        with (
            patch("app.services.providers.manager.data_manager.search_cities", new=AsyncMock(return_value=mock_city)),
            patch(
                "app.services.providers.manager.data_manager.get_unified_air_quality",
                new=AsyncMock(return_value=_make_mock_aq_response(us_epa_payload)),
            ),
        ):
            res = await ai_service.execute_tool("get_health_guidance", {"location": "TestCity", "activity": "running"})

        assert res["aqi"] is None
        assert res["category"] == "Unavailable"
        assert "Unavailable" in res["safety_assessment"]
        assert "Safe" not in res["safety_assessment"]

    valid_cases = [
        (0, "Good", "Safe"),
        (50, "Good", "Safe"),
        (100, "Moderate", "Acceptable with caution"),
        (125, "Unhealthy for Sensitive Groups", "Moderate Risk for sensitive groups"),
        (200, "Unhealthy", "Unhealthy - Avoid prolonged exertion"),
        (260, "Very Unhealthy", "Dangerous - Avoid outdoor activities"),
    ]

    for aqi_val, expected_cat, expected_safety in valid_cases:
        with (
            patch("app.services.providers.manager.data_manager.search_cities", new=AsyncMock(return_value=mock_city)),
            patch(
                "app.services.providers.manager.data_manager.get_unified_air_quality",
                new=AsyncMock(return_value=_make_mock_aq_response({"aqi": aqi_val, "category": expected_cat, "advisory": "Official note"})),
            ),
        ):
            res = await ai_service.execute_tool("get_health_guidance", {"location": "TestCity", "activity": "running"})

        assert res["aqi"] == aqi_val
        assert res["category"] == expected_cat
        assert res["safety_assessment"] == expected_safety


@pytest.mark.asyncio
async def test_ai_service_unavailable_never_fabricates_42_and_handles_null_tool_args():
    mock_city = [{"name": "TestCity", "latitude": 35.0, "longitude": 139.0}]
    unavail_resp = _make_mock_aq_response({"aqi": None, "category": "Unavailable", "advisory": None})
    with (
        patch("app.services.providers.manager.data_manager.search_cities", new=AsyncMock(return_value=mock_city)),
        patch("app.services.providers.manager.data_manager.get_unified_air_quality", new=AsyncMock(return_value=unavail_resp)),
    ):
        det = await ai_service._deterministic_reasoning("How is air in TestCity?", "TestCity")
        assert "42" not in det["response"]
        assert "Unavailable" in det["response"]
        assert "None" not in det["response"]
        assert det["grounding_data"]["aqi"] is None
        assert det["grounding_data"]["category"] == "Unavailable"
        assert det["grounding_data"]["dominant_pollutant"] == "Unavailable"

    # Non-string / null arguments must return clean error or safe default rather than AttributeError
    assert "error" in await ai_service.execute_tool("get_air_quality", {"location": None})
    assert "error" in await ai_service.execute_tool("get_pollution_trends", {"location": None, "pollutant": 123})
    with (
        patch("app.services.providers.manager.data_manager.search_cities", new=AsyncMock(return_value=mock_city)),
        patch("app.services.providers.manager.data_manager.get_unified_air_quality", new=AsyncMock(return_value=unavail_resp)),
    ):
        trend_res = await ai_service.execute_tool("get_pollution_trends", {"location": "TestCity", "pollutant": None})
        assert trend_res["pollutant"] == "pm25"
        health_res = await ai_service.execute_tool("get_health_guidance", {"location": "TestCity", "activity": 123})
        assert health_res["activity"] == "running"
