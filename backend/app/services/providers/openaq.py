import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.services.providers.base import EnvironmentalProvider, NormalizedMeasurement

class OpenAQProvider(EnvironmentalProvider):
    """
    OpenAQ API v3 client for physical ground-level environmental monitoring stations.
    Docs: https://docs.openaq.org/
    Authentication: X-API-Key header with OPENAQ_API_KEY
    """
    BASE_URL = "https://api.openaq.org/v3"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAQ_API_KEY

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "AeroSenseAI/1.0"
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def find_nearby_stations(self, lat: float, lon: float, radius_meters: int = 50000, limit: int = 10) -> List[Dict[str, Any]]:
        """Finds physical ground monitoring stations around coordinates."""
        if not self.api_key:
            return []

        endpoint = f"{self.BASE_URL}/locations"
        params = {
            "coordinates": f"{lat},{lon}",
            "radius": radius_meters,
            "limit": limit
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(endpoint, params=params, headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    stations = []
                    for loc in data.get("results", []):
                        stations.append({
                            "id": loc.get("id"),
                            "name": loc.get("name"),
                            "latitude": loc.get("coordinates", {}).get("latitude"),
                            "longitude": loc.get("coordinates", {}).get("longitude"),
                            "country": loc.get("country", {}).get("name") if isinstance(loc.get("country"), dict) else loc.get("country"),
                            "provider": loc.get("provider", {}).get("name") if isinstance(loc.get("provider"), dict) else "OpenAQ",
                            "sensors": loc.get("sensors", []),
                            "last_updated": loc.get("datetimeLast", {}).get("utc") if isinstance(loc.get("datetimeLast"), dict) else None,
                            "type": "ground_station"
                        })
                    return stations
                else:
                    print(f"[OpenAQ] Locations lookup returned status {resp.status_code}")
            except Exception as e:
                print(f"[OpenAQ] Exception in find_nearby_stations: {e}")
        return []

    async def get_current_air_quality(self, lat: float, lon: float, location_name: str = "") -> Optional[Dict[str, Any]]:
        """
        Attempts to find the nearest active physical ground station and fetch its latest measurements.
        """
        nearby = await self.find_nearby_stations(lat, lon, radius_meters=40000, limit=1)
        if not nearby:
            return None
            
        station = nearby[0]
        station_id = station["id"]
        endpoint = f"{self.BASE_URL}/locations/{station_id}/latest"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(endpoint, headers=self._get_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    measurements = {}
                    retrieval_time = datetime.now(timezone.utc)
                    
                    for item in data.get("results", []):
                        param = item.get("parameter", {}).get("name", "").lower()
                        val = item.get("value")
                        unit = item.get("unit", "ug/m3")
                        last_updated = item.get("datetime", {}).get("utc")
                        
                        try:
                            obs_time = datetime.fromisoformat(last_updated.replace("Z", "+00:00")) if last_updated else retrieval_time
                        except Exception:
                            obs_time = retrieval_time
                            
                        # Normalize parameter name
                        p_key = None
                        if "pm2.5" in param or "pm25" in param:
                            p_key = "pm25"
                        elif "pm10" in param:
                            p_key = "pm10"
                        elif "no2" in param:
                            p_key = "no2"
                        elif "so2" in param:
                            p_key = "so2"
                        elif "co" in param:
                            p_key = "co"
                        elif "o3" in param or "ozone" in param:
                            p_key = "o3"
                            
                        if p_key and val is not None and val >= 0:
                            measurements[p_key] = NormalizedMeasurement(
                                pollutant=p_key,
                                value=float(val),
                                unit=unit,
                                measurement_type="ground_observation",
                                source=f"OpenAQ / {station['name']} (Station ID: {station_id})",
                                data_quality="verified",
                                observation_timestamp=obs_time,
                                retrieval_timestamp=retrieval_time
                            )
                            
                    if measurements:
                        return {
                            "source": f"OpenAQ Ground Station: {station['name']}",
                            "station_id": station_id,
                            "station_name": station["name"],
                            "latitude": station["latitude"],
                            "longitude": station["longitude"],
                            "measurements": measurements,
                            "is_ground_observation": True
                        }
            except Exception as e:
                print(f"[OpenAQ] Latest measurements error: {e}")
                
        return None

    async def get_hourly_trends(self, lat: float, lon: float, past_days: int = 2, forecast_days: int = 3) -> Optional[Dict[str, Any]]:
        # OpenAQ v3 historical requires separate sensor queries; Open-Meteo handles continuous hourly trends
        return None

openaq_provider = OpenAQProvider()
