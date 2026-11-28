import logging
import math
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from app.core.config import settings
from app.core.redaction import format_safe_exception
from app.services.providers.base import EnvironmentalProvider, NormalizedMeasurement

logger = logging.getLogger(__name__)

_UNIT_ALIASES: Dict[str, str] = {
    "ug/m3": "ug/m3",
    "µg/m³": "ug/m3",
    "μg/m³": "ug/m3",
    "ug/m^3": "ug/m3",
    "mg/m3": "mg/m3",
    "mg/m³": "mg/m3",
    "mg/m^3": "mg/m3",
    "ppm": "ppm",
    "ppb": "ppb",
}

_GAS_POLLUTANTS = {"no2", "so2", "co", "o3"}


def _extract_finite_nonneg(raw: Any) -> Optional[float]:
    """Returns a non-negative finite float (preserving 0.0), or None for invalid/non-finite inputs."""
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    try:
        val = float(raw)
    except (OverflowError, ValueError, TypeError):
        return None
    if not math.isfinite(val) or val < 0:
        return None
    return 0.0 if val == 0 else val


def _canonicalize_unit(raw_unit: Optional[str]) -> Optional[str]:
    if not isinstance(raw_unit, str):
        return None
    cleaned = raw_unit.strip()
    if not cleaned:
        return None
    return _UNIT_ALIASES.get(cleaned.lower(), cleaned)


def _normalize_pollutant_key(param_name: str) -> Optional[str]:
    cleaned = param_name.strip().lower()
    if not cleaned:
        return None
    if "pm2.5" in cleaned or "pm25" in cleaned:
        return "pm25"
    if "pm10" in cleaned:
        return "pm10"
    if "no2" in cleaned:
        return "no2"
    if "so2" in cleaned:
        return "so2"
    if cleaned == "co" or "carbon monoxide" in cleaned:
        return "co"
    if "o3" in cleaned or "ozone" in cleaned:
        return "o3"
    return None


def _normalize_openaq_unit(
    pollutant: str,
    val: float,
    raw_unit: Optional[str],
) -> Tuple[Optional[float], str, str, str, str, str, Optional[str]]:
    """
    Applies justified metric mass conversions and preserves original volumetric/unsupported units
    without inventing temperature/pressure conversions or assuming ug/m3.

    Returns:
        (normalized_value, unit, measurement_type, data_quality, data_origin, conversion_method, conversion_assumption)
    """
    canonical_unit = _canonicalize_unit(raw_unit)
    target_unit = "mg/m3" if pollutant == "co" else "ug/m3"

    if canonical_unit is None:
        return (
            None,
            "unavailable",
            "unavailable",
            "unavailable",
            "unavailable",
            "none",
            "Missing sensor unit metadata; excluded from concentration calculations",
        )

    if canonical_unit == target_unit:
        return (val, target_unit, "ground_observation", "verified", "measured", "none", None)

    if pollutant == "co" and canonical_unit == "ug/m3":
        return (round(val / 1000.0, 4), "mg/m3", "ground_observation", "verified", "measured", "ugm3_to_mgm3", None)

    if pollutant != "co" and canonical_unit == "mg/m3":
        return (round(val * 1000.0, 4), "ug/m3", "ground_observation", "verified", "measured", "mgm3_to_ugm3", None)

    if pollutant in _GAS_POLLUTANTS and canonical_unit in {"ppm", "ppb"}:
        return (
            None,
            canonical_unit,
            "ground_observation",
            "provisional",
            "measured",
            "none",
            "Ambient temperature and pressure required for ppm/ppb mass conversion",
        )

    return (
        None,
        canonical_unit,
        "unavailable",
        "unavailable",
        "unavailable",
        "none",
        f"Unsupported unit '{canonical_unit}' for {pollutant}; excluded from concentration calculations",
    )

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
        if (
            isinstance(lat, bool)
            or isinstance(lon, bool)
            or not isinstance(lat, (int, float))
            or not isinstance(lon, (int, float))
            or not math.isfinite(float(lat))
            or not math.isfinite(float(lon))
            or float(lat) < -90.0
            or float(lat) > 90.0
            or float(lon) < -180.0
            or float(lon) > 180.0
        ):
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
                    logger.warning("[OpenAQ] Locations lookup returned status %s", resp.status_code)
            except Exception as e:
                logger.warning("[OpenAQ] Exception in find_nearby_stations: %s", format_safe_exception(e, [self.api_key]))
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

                    # Build sensorId -> metadata map from /v3/locations sensors array
                    sensors_by_id: Dict[Any, Dict[str, Any]] = {}
                    for sensor in station.get("sensors", []) or []:
                        if isinstance(sensor, dict) and sensor.get("id") is not None:
                            sensors_by_id[sensor.get("id")] = sensor

                    for item in data.get("results", []):
                        if not isinstance(item, dict):
                            continue
                        sensor_id = item.get("sensorsId") if item.get("sensorsId") is not None else item.get("sensorId")
                        sensor_meta = sensors_by_id.get(sensor_id, {})
                        sensor_param = sensor_meta.get("parameter") if isinstance(sensor_meta.get("parameter"), dict) else {}
                        item_param = item.get("parameter") if isinstance(item.get("parameter"), dict) else {}

                        param_raw = sensor_param.get("name") or item_param.get("name") or ""
                        p_key = _normalize_pollutant_key(str(param_raw))
                        if not p_key:
                            continue

                        val = _extract_finite_nonneg(item.get("value"))
                        if val is None:
                            continue

                        raw_unit = (
                            sensor_param.get("units")
                            or sensor_param.get("unit")
                            or item_param.get("units")
                            or item_param.get("unit")
                            or item.get("units")
                            or item.get("unit")
                        )

                        period_meta = sensor_meta.get("period") if isinstance(sensor_meta.get("period"), dict) else {}
                        item_period = item.get("period") if isinstance(item.get("period"), dict) else {}
                        averaging_period = (
                            period_meta.get("label")
                            or item_period.get("label")
                            or sensor_meta.get("reportingPeriod")
                            or "unknown"
                        )

                        dt_obj = item.get("datetime") if isinstance(item.get("datetime"), dict) else {}
                        last_updated = dt_obj.get("utc")
                        try:
                            obs_time = datetime.fromisoformat(last_updated.replace("Z", "+00:00")) if last_updated else retrieval_time
                            if obs_time.tzinfo is None:
                                obs_time = obs_time.replace(tzinfo=timezone.utc)
                        except Exception:
                            obs_time = retrieval_time

                        (
                            norm_val,
                            norm_unit,
                            meas_type,
                            data_quality,
                            data_origin,
                            conv_method,
                            conv_assumption,
                        ) = _normalize_openaq_unit(p_key, val, raw_unit)

                        new_meas = NormalizedMeasurement(
                            pollutant=p_key,
                            value=norm_val,
                            unit=norm_unit,
                            measurement_type=meas_type,
                            source=f"OpenAQ / {station['name']} (Station ID: {station_id})",
                            data_quality=data_quality,
                            observation_timestamp=obs_time,
                            retrieval_timestamp=retrieval_time,
                            original_value=val,
                            original_unit=raw_unit.strip() if isinstance(raw_unit, str) and raw_unit.strip() else None,
                            averaging_period=str(averaging_period),
                            data_origin=data_origin,
                            conversion_method=conv_method,
                            conversion_assumption=conv_assumption,
                        )

                        # Preserve an existing usable measured concentration if a duplicate sensor is unavailable/unconverted.
                        existing_meas = measurements.get(p_key)
                        if existing_meas is None or existing_meas.value is None or norm_val is not None:
                            measurements[p_key] = new_meas

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
                logger.warning("[OpenAQ] Latest measurements error: %s", format_safe_exception(e, [self.api_key]))
                
        return None

    async def get_hourly_trends(self, lat: float, lon: float, past_days: int = 2, forecast_days: int = 3) -> Optional[Dict[str, Any]]:
        # OpenAQ v3 historical requires separate sensor queries; Open-Meteo handles continuous hourly trends
        return None

openaq_provider = OpenAQProvider()
