from fastapi import APIRouter, Query
from typing import List, Dict, Any
from app.services.providers.open_meteo import open_meteo_provider
from app.services.providers.openaq import openaq_provider
from app.services.providers.waqi import waqi_provider

router = APIRouter(prefix="/locations", tags=["Locations"])

POPULAR_CITIES = [
    {"name": "Tokyo", "city": "Tokyo", "country": "Japan", "latitude": 35.6895, "longitude": 139.6917},
    {"name": "Delhi", "city": "Delhi", "country": "India", "latitude": 28.6139, "longitude": 77.2090},
    {"name": "London", "city": "London", "country": "United Kingdom", "latitude": 51.5074, "longitude": -0.1278},
    {"name": "New York", "city": "New York", "country": "United States", "latitude": 40.7128, "longitude": -74.0060},
    {"name": "Paris", "city": "Paris", "country": "France", "latitude": 48.8566, "longitude": 2.3522},
    {"name": "Sydney", "city": "Sydney", "country": "Australia", "latitude": -33.8688, "longitude": 151.2093},
    {"name": "Singapore", "city": "Singapore", "country": "Singapore", "latitude": 1.3521, "longitude": 103.8198},
    {"name": "Cairo", "city": "Cairo", "country": "Egypt", "latitude": 30.0444, "longitude": 31.2357},
    {"name": "Sao Paulo", "city": "Sao Paulo", "country": "Brazil", "latitude": -23.5505, "longitude": -46.6333},
    {"name": "Berlin", "city": "Berlin", "country": "Germany", "latitude": 52.5200, "longitude": 13.4050},
    {"name": "Beijing", "city": "Beijing", "country": "China", "latitude": 39.9042, "longitude": 116.4074},
    {"name": "Los Angeles", "city": "Los Angeles", "country": "United States", "latitude": 34.0522, "longitude": -118.2437}
]

@router.get("/search")
async def search_locations(q: str = Query(..., min_length=2, description="Search query for city or place")):
    results = await open_meteo_provider.search_locations(q, limit=8)
    return results

@router.get("/popular")
async def get_popular_cities():
    return POPULAR_CITIES

@router.get("/stations")
async def get_nearby_stations(
    lat: float = Query(..., ge=-90.0, le=90.0, allow_inf_nan=False),
    lon: float = Query(..., ge=-180.0, le=180.0, allow_inf_nan=False),
    radius: int = Query(50000, ge=100, le=500000, description="Radius in meters")
):
    """
    Retrieves authentic ground-level monitoring stations within geographic bounds.
    Queries WAQI as the primary physical sensor network.
    Never fabricates or generates synthetic stations.
    """
    stations = []
    provider_label = "None"
    
    # 1. Primary ground-station provider: WAQI
    try:
        stations = await waqi_provider.find_nearby_stations(lat, lon, radius_meters=radius, limit=40)
        if stations:
            provider_label = "WAQI Physical Sensor Network"
    except Exception:
        stations = []

    # 2. Secondary fallback if configured: OpenAQ
    if not stations:
        try:
            stations = await openaq_provider.find_nearby_stations(lat, lon, radius_meters=radius, limit=20)
            if stations:
                provider_label = "OpenAQ Global Repository"
        except Exception:
            stations = []

    # Return authentic stations only - never fabricate or interpolate
    return {
        "stations": stations,
        "count": len(stations),
        "provider": provider_label,
        "has_ground_data": len(stations) > 0
    }
