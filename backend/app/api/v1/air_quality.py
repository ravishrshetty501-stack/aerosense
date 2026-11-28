from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from app.services.providers.manager import data_manager
from app.services.aqi.engine import normalize_standard_name

router = APIRouter(prefix="/air-quality", tags=["Air Quality"])

@router.get("/current")
async def get_current_air_quality(
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0, allow_inf_nan=False),
    lon: Optional[float] = Query(None, ge=-180.0, le=180.0, allow_inf_nan=False),
    city: Optional[str] = Query(None),
    standard: str = Query("US_EPA", description="US_EPA, INDIA_CPCB, or EUROPEAN_AQI")
):
    if lat is None or lon is None:
        if not city:
            city = "Tokyo"
        locations = await data_manager.search_cities(city)
        if not locations:
            raise HTTPException(status_code=404, detail=f"Location '{city}' not found.")
        target = locations[0]
        lat = target["latitude"]
        lon = target["longitude"]
        city_name = target["name"]
    else:
        lat_fmt = round(0.0 if lat == 0 else lat, 2)
        lon_fmt = round(0.0 if lon == 0 else lon, 2)
        city_name = city or f"{lat_fmt}, {lon_fmt}"

    canonical_standard = normalize_standard_name(standard)
    response = await data_manager.get_unified_air_quality(lat, lon, city_name, canonical_standard)
    return response

@router.get("/history")
async def get_air_quality_history(
    lat: float = Query(..., ge=-90.0, le=90.0, allow_inf_nan=False),
    lon: float = Query(..., ge=-180.0, le=180.0, allow_inf_nan=False)
):
    response = await data_manager.get_unified_air_quality(lat, lon, "Query Location")
    return {"history": response.hourly_history}

@router.get("/forecast")
async def get_air_quality_forecast(
    lat: float = Query(..., ge=-90.0, le=90.0, allow_inf_nan=False),
    lon: float = Query(..., ge=-180.0, le=180.0, allow_inf_nan=False)
):
    response = await data_manager.get_unified_air_quality(lat, lon, "Query Location")
    return {"forecast": response.forecast}
