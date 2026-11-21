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
async def test_ai_chat_grounded_response():
    resp = await ai_service.chat("What is the current air quality in Tokyo and is it safe to run?")
    assert "response" in resp
    assert len(resp["response"]) > 50
    assert "Tokyo" in resp["response"]
