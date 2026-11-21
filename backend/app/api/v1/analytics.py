from fastapi import APIRouter, Query
from typing import List
from app.services.providers.manager import data_manager
from app.services.alert_service import alert_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/trends")
async def get_trends(
    lat: float = Query(...),
    lon: float = Query(...),
    city: str = Query("Query City")
):
    res = await data_manager.get_unified_air_quality(lat, lon, city)
    current_pm25 = res.measurements.get("pm25").value if res.measurements.get("pm25") else 0
    spike_info = alert_service.detect_spike(res.hourly_history or [], current_pm25, "pm25")
    
    return {
        "city": city,
        "history": res.hourly_history,
        "forecast": res.forecast,
        "spike_detected": spike_info is not None,
        "spike_info": spike_info
    }

@router.get("/compare")
async def compare_cities(
    cities: List[str] = Query(..., description="List of city names, e.g. ?cities=London&cities=Tokyo"),
    standard: str = Query("US_EPA")
):
    """
    Compares air quality across distinct cities.
    Enforces canonical deduplication so no city is analyzed or presented twice.
    """
    seen_canonical = set()
    unique_city_queries = []
    
    for c in cities:
        c_clean = c.strip()
        c_lower = c_clean.lower()
        if c_clean and c_lower not in seen_canonical:
            seen_canonical.add(c_lower)
            unique_city_queries.append(c_clean)

    results = []
    seen_coords = set()

    for c in unique_city_queries[:5]:
        locs = await data_manager.search_cities(c)
        if locs:
            t = locs[0]
            # Verify coordinates are not a duplicate of an already added city
            coord_key = (round(t["latitude"], 2), round(t["longitude"], 2))
            if coord_key in seen_coords:
                continue
            seen_coords.add(coord_key)

            aq_res = await data_manager.get_unified_air_quality(t["latitude"], t["longitude"], t["name"], standard)
            std_res = aq_res.aqi_standard_results.get(standard, {})
            results.append({
                "city": t["name"],
                "country": t.get("country"),
                "latitude": t["latitude"],
                "longitude": t["longitude"],
                "aqi": std_res.get("aqi"),
                "category": std_res.get("category"),
                "color": std_res.get("color"),
                "dominant_pollutant": aq_res.dominant_pollutant,
                "pm25": aq_res.measurements.get("pm25").value if aq_res.measurements.get("pm25") else None,
                "pm10": aq_res.measurements.get("pm10").value if aq_res.measurements.get("pm10") else None,
                "no2": aq_res.measurements.get("no2").value if aq_res.measurements.get("no2") else None,
                "o3": aq_res.measurements.get("o3").value if aq_res.measurements.get("o3") else None,
                "primary_source": aq_res.primary_source,
                "is_ground_observation": aq_res.is_ground_observation,
                "freshness_minutes": aq_res.data_freshness_minutes
            })

    return {"standard": standard, "comparison": results}
