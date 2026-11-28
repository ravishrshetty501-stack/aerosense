import logging
import math
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.core.redaction import format_safe_exception
from app.services.providers.base import EnvironmentalProvider, NormalizedMeasurement

logger = logging.getLogger(__name__)


def _extract_finite_nonneg(raw: Any) -> Optional[float]:
    """Returns a non-negative finite float (preserving genuine 0.0), or None for invalid/non-finite inputs."""
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    try:
        val = float(raw)
    except (OverflowError, ValueError, TypeError):
        return None
    if not math.isfinite(val) or val < 0:
        return None
    return 0.0 if val == 0 else val

class WAQIProvider(EnvironmentalProvider):
    """
    World Air Quality Index (WAQI / aqicn.org) API Provider.
    Provides instant real-time physical ground monitoring station data from 30,000+ stations worldwide.
    Free instant token available at: https://aqicn.org/data-platform/token/
    """
    BASE_URL = "https://api.waqi.info"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "WAQI_API_KEY", "")

    async def find_nearby_stations(self, lat: float, lon: float, radius_meters: int = 50000, limit: int = 40) -> List[Dict[str, Any]]:
        """
        Queries live monitoring stations within the bounding box of the given coordinates.
        Uses WAQI /v2/map/bounds/ endpoint.
        """
        if not self.api_key:
            return []

        # Convert radius in meters to approximate lat/lon degrees (1 deg ~ 111 km)
        try:
            r_meters = float(radius_meters)
        except Exception:
            r_meters = 50000.0
        delta = max(0.2, (r_meters / 111000.0) * 1.5)
        lat_min = lat - delta
        lat_max = lat + delta
        lon_min = lon - delta
        lon_max = lon + delta

        endpoint = f"{self.BASE_URL}/v2/map/bounds/"
        params = {
            "latlng": f"{lat_min},{lon_min},{lat_max},{lon_max}",
            "token": self.api_key
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(endpoint, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "ok":
                        stations = []
                        for st in data.get("data", [])[:limit]:
                            try:
                                aqi_val = int(st.get("aqi")) if str(st.get("aqi")).isdigit() else None
                            except Exception:
                                aqi_val = None

                            stations.append({
                                "id": st.get("uid"),
                                "name": st.get("station", {}).get("name", "Ground Sensor Station"),
                                "latitude": st.get("lat"),
                                "longitude": st.get("lon"),
                                "aqi": aqi_val,
                                "provider": "WAQI / Regional Environmental Agency",
                                "last_updated": st.get("station", {}).get("time"),
                                "type": "ground_station"
                            })
                        return stations
            except Exception as e:
                logger.warning("[WAQI] Exception querying station bounds: %s", format_safe_exception(e, [self.api_key]))
        return []

    async def get_current_air_quality(self, lat: float, lon: float, location_name: str = "") -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        endpoint = f"{self.BASE_URL}/feed/geo:{lat};{lon}/"
        params = {"token": self.api_key}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(endpoint, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "ok":
                        d = data.get("data", {})
                        station_name = d.get("city", {}).get("name", location_name)
                        iaqi = d.get("iaqi", {}) if isinstance(d.get("iaqi"), dict) else {}
                        retrieval_time = datetime.now(timezone.utc)
                        time_s = d.get("time", {}).get("iso") if isinstance(d.get("time"), dict) else None
                        try:
                            obs_time = datetime.fromisoformat(time_s) if time_s else retrieval_time
                        except Exception:
                            obs_time = retrieval_time

                        overall_aqi = _extract_finite_nonneg(d.get("aqi"))
                        raw_dom = d.get("dominentpol")
                        dominant_pol = (
                            raw_dom.strip().lower()
                            if isinstance(raw_dom, str) and raw_dom.strip()
                            else None
                        )

                        # WAQI iaqi.<pol>.v values are provider-calculated AQI sub-indices (not raw concentrations).
                        # Preserve them in provider_aqi_subindex / provider_subindices while keeping value=None so
                        # concentration-based AQI breakpoint tables never double-index provider AQI scores.
                        measurements: Dict[str, NormalizedMeasurement] = {}
                        provider_subindices: Dict[str, float] = {}
                        mapping = {
                            "pm25": "pm25",
                            "pm10": "pm10",
                            "no2": "no2",
                            "so2": "so2",
                            "co": "co",
                            "o3": "o3",
                        }
                        for std_key, waqi_key in mapping.items():
                            val_obj = iaqi.get(waqi_key)
                            if not isinstance(val_obj, dict) or "v" not in val_obj:
                                continue
                            subindex_val = _extract_finite_nonneg(val_obj.get("v"))
                            if subindex_val is None:
                                continue
                            provider_subindices[std_key] = subindex_val
                            measurements[std_key] = NormalizedMeasurement(
                                pollutant=std_key,
                                value=None,
                                unit="aqi_subindex",
                                measurement_type="ground_observation",
                                source=f"WAQI Ground Station ({station_name})",
                                data_quality="verified",
                                observation_timestamp=obs_time,
                                retrieval_timestamp=retrieval_time,
                                original_value=subindex_val,
                                original_unit="waqi_iaqi_subindex",
                                averaging_period="provider_reported",
                                data_origin="provider_index",
                                provider_aqi_subindex=subindex_val,
                                conversion_method="none",
                            )

                        if overall_aqi is not None or provider_subindices:
                            return {
                                "source": f"WAQI Ground Station ({station_name})",
                                "station_name": station_name,
                                "latitude": lat,
                                "longitude": lon,
                                "provider_aqi": overall_aqi,
                                "dominant_pollutant": dominant_pol,
                                "provider_subindices": provider_subindices,
                                "measurements": measurements,
                                "observation_time": obs_time,
                                "is_ground_observation": True,
                            }
            except Exception as e:
                logger.warning("[WAQI] Exception querying air quality: %s", format_safe_exception(e, [self.api_key]))
        return None

    async def get_hourly_trends(self, lat: float, lon: float, past_days: int = 2, forecast_days: int = 3) -> Optional[Dict[str, Any]]:
        return None

waqi_provider = WAQIProvider()
