from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from app.services.providers.manager import data_manager

router = APIRouter(prefix="/air-quality", tags=["Air Quality"])

@router.get("/current")
async def get_current_air_quality(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
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
        city_name = city or f"{round(lat, 2)}, {round(lon, 2)}"
        
    response = await data_manager.get_unified_air_quality(lat, lon, city_name, standard)
    return response

@router.get("/history")
async def get_air_quality_history(
    lat: float = Query(...),
    lon: float = Query(...)
):
    response = await data_manager.get_unified_air_quality(lat, lon, "Query Location")
    return {"history": response.hourly_history}

@router.get("/forecast")
async def get_air_quality_forecast(
    lat: float = Query(...),
    lon: float = Query(...)
):
    response = await data_manager.get_unified_air_quality(lat, lon, "Query Location")
    return {"forecast": response.forecast}
