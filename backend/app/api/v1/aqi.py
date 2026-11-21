from fastapi import APIRouter, Body
from typing import Dict, Any
from app.services.aqi.engine import aqi_engine

router = APIRouter(prefix="/aqi", tags=["AQI Calculation Engine"])

@router.post("/calculate")
async def calculate_aqi(
    measurements: Dict[str, float] = Body(...),
    standard: str = "US_EPA"
):
    result = aqi_engine.calculate(measurements, standard)
    return result

@router.post("/compare-standards")
async def compare_all_standards(
    measurements: Dict[str, float] = Body(...)
):
    return aqi_engine.calculate_all_standards(measurements)
