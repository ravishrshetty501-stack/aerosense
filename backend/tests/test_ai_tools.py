import pytest
from app.services.ai_service import ai_service

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
