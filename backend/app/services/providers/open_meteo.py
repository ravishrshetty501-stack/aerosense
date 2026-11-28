import asyncio
import logging
import math
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from app.core.redaction import format_safe_exception
from app.services.providers.base import EnvironmentalProvider, LocationInfo, NormalizedMeasurement

logger = logging.getLogger(__name__)


@dataclass
class _CacheEntry:
    """Atomic cache entry bundling payload with its UTC expiration timestamp."""
    data: Dict[str, Any]
    expires_at: datetime


class _CoordinateLockEntry:
    """Reference-counted lock entry so idle coordinate locks are cleaned up safely."""
    __slots__ = ("lock", "ref_count")

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.ref_count: int = 0


class OpenMeteoAirQualityProvider(EnvironmentalProvider):
    """
    Open-Meteo Air Quality API client.
    Provides global hourly estimates, forecast, and historical reanalysis for PM2.5, PM10, NO2, SO2, CO, O3, US AQI, and European AQI.
    Docs: https://open-meteo.com/en/docs/air-quality-api

    Cache capacity & eviction rationale:
    - Normalized coordinates round to 0.1 degrees (~11 km atmospheric grid cells).
    - DEFAULT_MAX_CACHE_SIZE = 256 bounds peak memory (~5-15 MB for 120h series payloads)
      on constrained cloud containers (e.g., 512 MB Render instances) while covering all
      preset metropolises, multi-city comparisons, and concurrent user queries.
    - Expired entries are purged proactively on reads, writes, and status checks using
      timezone-aware UTC timestamps before LRU eviction is applied.
    """

    BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    DEFAULT_HEADERS = {
        "User-Agent": "AeroSense-AI/1.0 (https://github.com/ravishrshetty501-stack/aerosense)"
    }
    DEFAULT_CACHE_TTL_SECONDS: float = 1800.0  # 30 minutes TTL for atmospheric reanalysis & forecast
    DEFAULT_MAX_CACHE_SIZE: int = 256

    def __init__(
        self,
        cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS,
        max_cache_size: int = DEFAULT_MAX_CACHE_SIZE,
    ):
        if isinstance(cache_ttl, bool) or not isinstance(cache_ttl, (int, float)):
            raise TypeError("cache_ttl must be a finite, positive number")
        ttl_seconds = float(cache_ttl)
        if not math.isfinite(ttl_seconds) or ttl_seconds <= 0.0:
            raise ValueError("cache_ttl must be a finite, positive number")
        if isinstance(max_cache_size, bool) or not isinstance(max_cache_size, int):
            raise TypeError("max_cache_size must be a positive integer")
        if max_cache_size < 1:
            raise ValueError("max_cache_size must be at least 1")
        self._cache: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._cache_ttl: float = ttl_seconds
        self._max_cache_size: int = max_cache_size
        self._coord_locks: Dict[str, _CoordinateLockEntry] = {}

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _make_cache_key(lat: float, lon: float) -> str:
        return f"{round(lat, 1)}_{round(lon, 1)}"

    def _purge_expired(self, now: Optional[datetime] = None) -> None:
        current = now if now is not None else self._utc_now()
        expired_keys = [
            key for key, entry in self._cache.items() if current >= entry.expires_at
        ]
        for key in expired_keys:
            del self._cache[key]

    def _get_valid_cached(self, cache_key: str, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        current = now if now is not None else self._utc_now()
        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        if current >= entry.expires_at:
            del self._cache[cache_key]
            return None
        self._cache.move_to_end(cache_key)
        return entry.data

    def _set_cached(self, cache_key: str, data: Dict[str, Any], now: Optional[datetime] = None) -> None:
        current = now if now is not None else self._utc_now()
        self._purge_expired(current)
        expires_at = current + timedelta(seconds=self._cache_ttl)
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
        self._cache[cache_key] = _CacheEntry(data=data, expires_at=expires_at)
        while len(self._cache) > self._max_cache_size:
            self._cache.popitem(last=False)

    def has_cached_data(self) -> bool:
        """
        Public read-only check indicating whether at least one valid (non-expired)
        cached telemetry entry is currently available.
        """
        self._purge_expired()
        return len(self._cache) > 0

    def cache_size(self) -> int:
        """
        Returns the count of currently valid (non-expired) cache entries.
        """
        self._purge_expired()
        return len(self._cache)

    @asynccontextmanager
    async def _acquire_coordinate_lock(self, cache_key: str) -> AsyncIterator[None]:
        entry = self._coord_locks.get(cache_key)
        if entry is None:
            entry = _CoordinateLockEntry()
            self._coord_locks[cache_key] = entry
        entry.ref_count += 1
        try:
            async with entry.lock:
                yield
        finally:
            entry.ref_count -= 1
            if entry.ref_count == 0 and self._coord_locks.get(cache_key) is entry:
                del self._coord_locks[cache_key]

    async def search_locations(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(headers=self.DEFAULT_HEADERS, timeout=10.0) as client:
            try:
                resp = await client.get(
                    self.GEOCODING_URL,
                    params={"name": query, "count": limit, "language": "en", "format": "json"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for item in data.get("results", []):
                        results.append({
                            "name": item.get("name"),
                            "city": item.get("name"),
                            "country": item.get("country"),
                            "country_code": item.get("country_code"),
                            "latitude": item.get("latitude"),
                            "longitude": item.get("longitude"),
                            "timezone": item.get("timezone", "UTC")
                        })
                    return results
            except Exception as e:
                logger.warning("[OpenMeteo] Geocoding lookup error: %s", format_safe_exception(e))
        return []

    async def get_current_air_quality(self, lat: float, lon: float, location_name: str = "") -> Optional[Dict[str, Any]]:
        """
        Retrieves current air quality estimates and hourly series from Open-Meteo.
        Uses bounded LRU TTL caching and per-coordinate locking to coalesce concurrent
        requests for identical grid cells without blocking unrelated coordinates.
        """
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
            return None

        cache_key = self._make_cache_key(lat, lon)
        cached = self._get_valid_cached(cache_key)
        if cached is not None:
            return cached

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi,european_aqi",
            "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi,european_aqi",
            "past_days": 2,
            "forecast_days": 3,
            "timezone": "UTC"
        }

        async with self._acquire_coordinate_lock(cache_key):
            # Re-check cache under per-coordinate lock to coalesce concurrent requests
            cached = self._get_valid_cached(cache_key)
            if cached is not None:
                return cached

            async with httpx.AsyncClient(headers=self.DEFAULT_HEADERS, timeout=12.0) as client:
                try:
                    resp = await client.get(self.BASE_URL, params=params)
                    if resp.status_code == 429:
                        logger.warning("[OpenMeteo] Rate limit (HTTP 429) for (%s, %s). Backing off 1.5s...", lat, lon)
                        await asyncio.sleep(1.5)
                        resp = await client.get(self.BASE_URL, params=params)

                    if resp.status_code != 200:
                        logger.warning("[OpenMeteo] API error: status %s for (%s, %s)", resp.status_code, lat, lon)
                        return None

                    data = resp.json()
                    current_raw = data.get("current", {})
                    current_units = data.get("current_units", {})
                    hourly_units = data.get("hourly_units", {})
                    utc_offset_seconds = data.get("utc_offset_seconds", 0)
                    obs_time_str = current_raw.get("time")

                    retrieval_time = self._utc_now()
                    parsed_obs_time = parse_utc_timestamp(obs_time_str, utc_offset_seconds)
                    obs_time = parsed_obs_time if parsed_obs_time is not None else retrieval_time

                    # Normalize pollutants
                    mapping = {
                        "pm25": ("pm2_5", current_units.get("pm2_5", "ug/m3")),
                        "pm10": ("pm10", current_units.get("pm10", "ug/m3")),
                        "no2":  ("nitrogen_dioxide", current_units.get("nitrogen_dioxide", "ug/m3")),
                        "so2":  ("sulphur_dioxide", current_units.get("sulphur_dioxide", "ug/m3")),
                        "co":   ("carbon_monoxide", current_units.get("carbon_monoxide", "ug/m3")),
                        "o3":   ("ozone", current_units.get("ozone", "ug/m3")),
                    }

                    measurements = {}
                    for standard_key, (api_key, default_unit) in mapping.items():
                        raw_val = current_raw.get(api_key)
                        if (
                            raw_val is None
                            or isinstance(raw_val, bool)
                            or not isinstance(raw_val, (int, float))
                        ):
                            continue
                        try:
                            raw_num = float(raw_val)
                        except (OverflowError, ValueError, TypeError):
                            continue
                        if not math.isfinite(raw_num) or raw_num < 0:
                            continue
                        raw_num = 0.0 if raw_num == 0 else raw_num

                        raw_unit = current_units.get(api_key, default_unit)
                        val = raw_num
                        unit = raw_unit
                        conversion_method = "none"
                        if standard_key == "co" and raw_unit in ("μg/m³", "µg/m³", "ug/m3"):
                            val = round(raw_num / 1000.0, 4)
                            unit = "mg/m3"
                            conversion_method = "ugm3_to_mgm3"
                        elif raw_unit in ("μg/m³", "µg/m³"):
                            unit = "ug/m3"

                        measurements[standard_key] = NormalizedMeasurement(
                            pollutant=standard_key,
                            value=val,
                            unit=unit,
                            measurement_type="model_estimate",
                            source="Open-Meteo CAMS Ensemble",
                            data_quality="verified",
                            observation_timestamp=obs_time,
                            retrieval_timestamp=retrieval_time,
                            original_value=raw_num,
                            original_unit=raw_unit,
                            averaging_period="instantaneous",
                            data_origin="model_derived",
                            conversion_method=conversion_method,
                        )

                    # Extract, UTC-normalize, deduplicate, and chronologically sort hourly trends & forecast
                    hourly_data = data.get("hourly", {})
                    times = hourly_data.get("time", []) or []
                    hourly_pm25 = hourly_data.get("pm2_5", []) or []
                    hourly_pm10 = hourly_data.get("pm10", []) or []
                    hourly_no2 = hourly_data.get("nitrogen_dioxide", []) or []
                    hourly_o3 = hourly_data.get("ozone", []) or []
                    hourly_us_aqi = hourly_data.get("us_aqi", []) or []

                    deduped_by_utc: Dict[datetime, Dict[str, Any]] = {}
                    for i, raw_t in enumerate(times):
                        pt_utc = parse_utc_timestamp(raw_t, utc_offset_seconds)
                        if pt_utc is None:
                            continue

                        candidate = {
                            "pm25": _coerce_finite_non_negative(hourly_pm25[i]) if i < len(hourly_pm25) else None,
                            "pm10": _coerce_finite_non_negative(hourly_pm10[i]) if i < len(hourly_pm10) else None,
                            "no2": _coerce_finite_non_negative(hourly_no2[i]) if i < len(hourly_no2) else None,
                            "o3": _coerce_finite_non_negative(hourly_o3[i]) if i < len(hourly_o3) else None,
                            "us_aqi": _coerce_finite_non_negative(hourly_us_aqi[i]) if i < len(hourly_us_aqi) else None,
                        }
                        if pt_utc in deduped_by_utc:
                            existing = deduped_by_utc[pt_utc]
                            for key, val in candidate.items():
                                if val is not None:
                                    existing[key] = val
                        else:
                            deduped_by_utc[pt_utc] = candidate

                    trend_records = []
                    for pt_utc in sorted(deduped_by_utc.keys()):
                        vals = deduped_by_utc[pt_utc]
                        is_future = pt_utc > obs_time
                        trend_records.append({
                            "time": pt_utc.isoformat(),
                            "pm25": vals["pm25"],
                            "pm10": vals["pm10"],
                            "no2": vals["no2"],
                            "o3": vals["o3"],
                            "us_aqi": vals["us_aqi"],
                            "is_forecast": is_future,
                            "type": "forecast" if is_future else "model_estimate"
                        })

                    rolling_o3_8h = compute_rolling_8h_ozone(
                        trend_records,
                        obs_time,
                        hourly_o3_unit=hourly_units.get("ozone") if isinstance(hourly_units, dict) else None,
                    )

                    result_data = {
                        "source": "Open-Meteo Air Quality",
                        "latitude": lat,
                        "longitude": lon,
                        "elevation": data.get("elevation", 0),
                        "timezone": "UTC",
                        "provider_reported_timezone": data.get("timezone", "UTC"),
                        "utc_offset_seconds": 0,
                        "observation_time": obs_time,
                        "retrieval_time": retrieval_time,
                        "measurements": measurements,
                        "provider_us_aqi": current_raw.get("us_aqi"),
                        "provider_european_aqi": current_raw.get("european_aqi"),
                        "rolling_o3_8h": rolling_o3_8h,
                        "hourly_series": trend_records
                    }
                    self._set_cached(cache_key, result_data)
                    return result_data
                except Exception as e:
                    logger.warning("[OpenMeteo] Exception querying air quality for (%s, %s): %s", lat, lon, format_safe_exception(e))
                    return None

    async def get_hourly_trends(self, lat: float, lon: float, past_days: int = 2, forecast_days: int = 3) -> Optional[Dict[str, Any]]:
        res = await self.get_current_air_quality(lat, lon)
        if res and "hourly_series" in res:
            return {"hourly_series": res["hourly_series"]}
        return None


import math
from datetime import datetime, timedelta, timezone


def _coerce_offset_seconds(utc_offset_seconds: Any) -> float:
    """Validate finite numeric UTC offset seconds without treating bools as ints."""
    if isinstance(utc_offset_seconds, bool) or utc_offset_seconds is None:
        return 0.0
    try:
        offset = float(utc_offset_seconds)
    except (TypeError, ValueError):
        return 0.0
    return offset if math.isfinite(offset) else 0.0


def _coerce_finite_non_negative(value: Any) -> Optional[float]:
    """Return finite non-negative float (preserving 0.0) or None for invalid inputs."""
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric < 0.0:
        return None
    return numeric


def parse_utc_timestamp(raw_time: Any, utc_offset_seconds: Any = 0) -> Optional[datetime]:
    """Normalize an Open-Meteo timestamp or datetime object to timezone-aware UTC."""
    if isinstance(raw_time, datetime):
        parsed = raw_time
    elif isinstance(raw_time, str):
        text = raw_time.strip()
        if not text:
            return None
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc)

    offset = _coerce_offset_seconds(utc_offset_seconds)
    return parsed.replace(tzinfo=timezone(timedelta(seconds=offset))).astimezone(timezone.utc)


def compute_rolling_8h_ozone(
    hourly_series: Optional[List[Dict[str, Any]]],
    target_time_utc: Any,
    hourly_o3_unit: Optional[str] = None,
    min_required_hours: int = 6,
) -> Dict[str, Any]:
    """
    Compute a model-derived trailing 8-hour rolling ozone mean in UTC.

    Product policy (non-regulatory):
    - Applies Open-Meteo CAMS ensemble hourly outputs only (never synthesized fallback series
      and never instantaneous `current.ozone` fallback).
    - Anchors the trailing 8-hour window to [T_end - 7h, T_end], where T_end is target_time_utc
      floored to the UTC hour boundary.
    - Requires `min_required_hours` (default 6 of 8 distinct hourly slots) with valid finite
      non-negative values (preserving 0.0).
    """
    obs_utc = parse_utc_timestamp(target_time_utc)
    if obs_utc is None:
        obs_utc = datetime.now(timezone.utc)

    window_end = obs_utc.replace(minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(hours=7)

    base_meta: Dict[str, Any] = {
        "pollutant": "o3",
        "value": None,
        "unit": "ug/m3",
        "status": "unavailable",
        "unavailable_reason": None,
        "averaging_period": "8h",
        "window_hours": 8,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "valid_hours": 0,
        "expected_hours": 8,
        "completeness_ratio": 0.0,
        "min_required_hours": min_required_hours,
        "completeness_policy": "model_derived_6_of_8_completeness",
        "is_regulatory_observation": False,
        "data_origin": "model_derived",
        "measurement_type": "unavailable",
        "source": "Open-Meteo CAMS Ensemble",
        "note": (
            "Model-derived trailing 8-hour rolling O3 estimate (6-of-8 completeness policy); "
            "not a regulatory ground-monitor observation."
        ),
    }

    if hourly_o3_unit is not None:
        normalized_unit = (
            str(hourly_o3_unit).strip().lower().replace("µ", "u").replace("³", "3")
        )
        if normalized_unit not in {"", "ug/m3"}:
            base_meta["unavailable_reason"] = "unsupported_hourly_o3_unit"
            return base_meta

    if not hourly_series:
        base_meta["unavailable_reason"] = "no_hourly_observations"
        return base_meta

    slot_values: Dict[datetime, float] = {}
    for item in hourly_series:
        if not isinstance(item, dict):
            continue
        if item.get("is_forecast") is True:
            continue
        item_type = str(item.get("type", "")).strip().lower()
        if item_type in {"forecast", "synthesized"}:
            continue

        pt_utc = parse_utc_timestamp(item.get("time"))
        if pt_utc is None or pt_utc > obs_utc:
            continue

        slot_utc = pt_utc.replace(minute=0, second=0, microsecond=0)
        if slot_utc < window_start or slot_utc > window_end:
            continue

        o3_val = _coerce_finite_non_negative(item.get("o3"))
        if o3_val is None:
            continue

        slot_values[slot_utc] = o3_val

    valid_hours = len(slot_values)
    base_meta["valid_hours"] = valid_hours
    base_meta["completeness_ratio"] = round(valid_hours / 8.0, 4)

    if valid_hours == 0:
        base_meta["unavailable_reason"] = "no_valid_hourly_o3_in_window"
        return base_meta

    if valid_hours < min_required_hours:
        base_meta["unavailable_reason"] = "insufficient_valid_hours"
        return base_meta

    mean_o3 = round(sum(slot_values.values()) / valid_hours, 4)
    return {
        **base_meta,
        "value": mean_o3,
        "status": "available",
        "unavailable_reason": None,
        "measurement_type": "model_estimate",
    }


open_meteo_provider = OpenMeteoAirQualityProvider()
