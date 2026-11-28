from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.providers.manager import EnvironmentalDataManager
from app.services.providers.open_meteo import (
    OpenMeteoAirQualityProvider,
    compute_rolling_8h_ozone,
    parse_utc_timestamp,
)


def _mock_httpx_get(payload: Dict[str, Any]):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return AsyncMock(return_value=resp)


def _build_open_meteo_payload(
    *,
    current_time: str,
    hourly_times: List[str],
    hourly_o3: List[Any],
    current_o3: float = 120.0,
    timezone_name: str = "UTC",
    utc_offset_seconds: int = 0,
    hourly_pm25: List[Any] | None = None,
) -> Dict[str, Any]:
    return {
        "latitude": 28.6139,
        "longitude": 77.2090,
        "elevation": 216.0,
        "timezone": timezone_name,
        "utc_offset_seconds": utc_offset_seconds,
        "current_units": {
            "pm2_5": "µg/m³",
            "pm10": "µg/m³",
            "nitrogen_dioxide": "µg/m³",
            "sulphur_dioxide": "µg/m³",
            "carbon_monoxide": "µg/m³",
            "ozone": "µg/m³",
        },
        "current": {
            "time": current_time,
            "pm2_5": 42.0,
            "pm10": 80.0,
            "nitrogen_dioxide": 25.0,
            "sulphur_dioxide": 10.0,
            "carbon_monoxide": 500.0,
            "ozone": current_o3,
            "us_aqi": 117,
            "european_aqi": 60,
        },
        "hourly_units": {
            "pm2_5": "µg/m³",
            "pm10": "µg/m³",
            "nitrogen_dioxide": "µg/m³",
            "ozone": "µg/m³",
        },
        "hourly": {
            "time": hourly_times,
            "pm2_5": hourly_pm25 if hourly_pm25 is not None else [30.0] * len(hourly_times),
            "pm10": [60.0] * len(hourly_times),
            "nitrogen_dioxide": [20.0] * len(hourly_times),
            "ozone": hourly_o3,
            "us_aqi": [90] * len(hourly_times),
        },
    }


@pytest.mark.asyncio
async def test_open_meteo_requests_utc_timezone_and_attaches_8h_rolling_o3():
    provider = OpenMeteoAirQualityProvider()
    end_utc = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)
    times = [(end_utc - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(7, -1, -1)]
    o3_vals = [40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 110.0]
    payload = _build_open_meteo_payload(
        current_time="2026-11-27T15:00",
        hourly_times=times,
        hourly_o3=o3_vals,
        current_o3=199.0,
    )

    mock_get = _mock_httpx_get(payload)
    with patch("httpx.AsyncClient.get", mock_get):
        result = await provider.get_current_air_quality(28.6139, 77.2090)

    assert result is not None
    assert mock_get.call_args.kwargs["params"]["timezone"] == "UTC"
    assert result["observation_time"] == end_utc
    assert result["observation_time"].tzinfo == timezone.utc

    # Current snapshot measurement stays instantaneous (no silent substitution)
    assert result["measurements"]["o3"].value == pytest.approx(199.0)
    assert result["measurements"]["o3"].averaging_period == "instantaneous"
    assert result["measurements"]["o3"].data_origin == "model_derived"

    rolling = result["rolling_o3_8h"]
    assert rolling["status"] == "available"
    assert rolling["value"] == pytest.approx(75.0)
    assert rolling["valid_hours"] == 8
    assert rolling["expected_hours"] == 8
    assert rolling["completeness_ratio"] == pytest.approx(1.0)
    assert rolling["averaging_period"] == "8h"
    assert rolling["data_origin"] == "model_derived"
    assert rolling["is_regulatory_observation"] is False
    assert rolling["completeness_policy"] == "model_derived_6_of_8_completeness"
    assert rolling["window_start"] == "2026-11-27T08:00:00+00:00"
    assert rolling["window_end"] == "2026-11-27T15:00:00+00:00"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tz_name", "utc_offset_sec", "local_obs_str", "expected_utc"),
    [
        ("Asia/Kolkata", 19800, "2026-11-27T17:30", datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)),
        ("America/New_York", -18000, "2026-11-27T07:00", datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)),
    ],
)
async def test_freshness_accurate_for_positive_and_negative_utc_offsets(
    tz_name: str,
    utc_offset_sec: int,
    local_obs_str: str,
    expected_utc: datetime,
):
    provider = OpenMeteoAirQualityProvider()
    # Build 8 hourly local timestamps converted cleanly via utc_offset_seconds
    local_obs = datetime.fromisoformat(local_obs_str)
    hourly_local = [(local_obs - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(7, -1, -1)]
    payload = _build_open_meteo_payload(
        current_time=local_obs_str,
        hourly_times=hourly_local,
        hourly_o3=[50.0] * 8,
        timezone_name=tz_name,
        utc_offset_seconds=utc_offset_sec,
    )

    with patch("httpx.AsyncClient.get", _mock_httpx_get(payload)):
        meteo_data = await provider.get_current_air_quality(19.076, 72.8777)

    assert meteo_data is not None
    assert meteo_data["observation_time"] == expected_utc
    assert meteo_data["measurements"]["pm25"].observation_timestamp == expected_utc

    manager = EnvironmentalDataManager()
    fixed_now = expected_utc + timedelta(minutes=12)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is not None else fixed_now.replace(tzinfo=None)

    with (
        patch("app.services.providers.manager.openaq_provider.get_current_air_quality", new=AsyncMock(return_value=None)),
        patch("app.services.providers.manager.waqi_provider.get_current_air_quality", new=AsyncMock(return_value=None)),
        patch("app.services.providers.manager.open_meteo_provider.get_current_air_quality", new=AsyncMock(return_value=meteo_data)),
        patch("app.services.providers.manager.datetime", _FixedDatetime),
    ):
        unified = await manager.get_unified_air_quality(19.076, 72.8777, "TestCity")

    # Regardless of +05:30 or -05:00 local offset, UTC freshness must be 12 minutes
    assert unified.data_freshness_minutes == 12
    assert unified.model_derived_aggregates is not None
    assert unified.model_derived_aggregates["o3_8h"]["status"] == "available"
    assert unified.model_derived_aggregates["o3_8h"]["value"] == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_dst_transition_hours_in_utc_have_no_duplicates_or_missing_hours():
    # US Fall-back DST transition: 2026-11-01 03:00Z..10:00Z spans 01:00 EDT -> 01:00 EST seamlessly in UTC
    provider = OpenMeteoAirQualityProvider()
    end_utc = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    times = [(end_utc - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(7, -1, -1)]
    o3_vals = [20.0, 22.0, 24.0, 26.0, 28.0, 30.0, 32.0, 34.0]
    payload = _build_open_meteo_payload(
        current_time="2026-11-01T10:00",
        hourly_times=times,
        hourly_o3=o3_vals,
    )

    with patch("httpx.AsyncClient.get", _mock_httpx_get(payload)):
        res = await provider.get_current_air_quality(40.7128, -74.0060)

    assert res is not None
    rolling = res["rolling_o3_8h"]
    assert rolling["valid_hours"] == 8
    assert rolling["status"] == "available"
    assert rolling["value"] == pytest.approx(sum(o3_vals) / 8.0)
    assert len({item["time"] for item in res["hourly_series"]}) == 8


@pytest.mark.asyncio
async def test_unsorted_duplicate_and_longer_hourly_o3_series_are_sorted_and_deduplicated():
    provider = OpenMeteoAirQualityProvider()
    # Out-of-order + duplicate timestamp + pm2_5 shorter than times + explicit offset on forecast point
    times = [
        "2026-11-27T14:00Z",
        "2026-11-27T09:00Z",
        "2026-11-27T12:00Z",
        "2026-11-27T12:00+00:00",  # duplicate UTC instant with updated O3
        "2026-11-27T15:00Z",
        "2026-11-27T16:00+00:00",  # forecast (> obs_time 15:00Z)
        "2026-11-27T10:00Z",
        "2026-11-27T11:00Z",
        "2026-11-27T13:00Z",
        "2026-11-27T08:00Z",
    ]
    o3_vals = [70.0, 20.0, 999.0, 50.0, 80.0, 250.0, 30.0, 40.0, 60.0, 10.0]
    payload = _build_open_meteo_payload(
        current_time="2026-11-27T15:00Z",
        hourly_times=times,
        hourly_o3=o3_vals,
        hourly_pm25=[11.0, 12.0],  # intentionally shorter than `times`
    )

    with patch("httpx.AsyncClient.get", _mock_httpx_get(payload)):
        res = await provider.get_current_air_quality(28.6139, 77.2090)

    assert res is not None
    series = res["hourly_series"]
    parsed_times = [parse_utc_timestamp(item["time"]) for item in series]
    assert parsed_times == sorted(parsed_times)
    assert len(series) == 9  # 8 historical + 1 forecast after deduplicating 12:00Z
    assert series[-1]["is_forecast"] is True
    assert all(not item["is_forecast"] for item in series[:-1])

    # Duplicate 12:00Z resolved to latest valid (50.0), forecast 16:00Z excluded
    rolling = res["rolling_o3_8h"]
    assert rolling["status"] == "available"
    assert rolling["valid_hours"] == 8
    assert rolling["value"] == pytest.approx((10 + 20 + 30 + 40 + 50 + 60 + 70 + 80) / 8.0)


def test_rolling_8h_o3_accepts_6_of_8_and_rejects_5_of_8():
    end_utc = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)
    # 6 of 8 valid hours -> accepted
    series_6 = [
        {"time": (end_utc - timedelta(hours=h)).isoformat(), "o3": 60.0, "is_forecast": False}
        for h in [7, 6, 4, 3, 1, 0]
    ]
    res_6 = compute_rolling_8h_ozone(series_6, end_utc)
    assert res_6["status"] == "available"
    assert res_6["valid_hours"] == 6
    assert res_6["completeness_ratio"] == pytest.approx(0.75)
    assert res_6["value"] == pytest.approx(60.0)

    # 5 of 8 valid hours -> rejected
    series_5 = series_6[:5]
    res_5 = compute_rolling_8h_ozone(series_5, end_utc)
    assert res_5["status"] == "unavailable"
    assert res_5["unavailable_reason"] == "insufficient_valid_hours"
    assert res_5["valid_hours"] == 5
    assert res_5["value"] is None


def test_rolling_8h_o3_rejects_out_of_window_points_and_excessive_gaps():
    end_utc = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)
    # Total 9 points exist, 4 are older than [T-7h, T] (at -11h..-8h) and 5 inside [T-7h, T]
    # Must NOT pull older points into the trailing 8h window to satisfy 6/8
    out_of_window_plus_5 = [
        {"time": (end_utc - timedelta(hours=h)).isoformat(), "o3": 90.0, "is_forecast": False}
        for h in [11, 10, 9, 8, 4, 3, 2, 1, 0]
    ]
    res = compute_rolling_8h_ozone(out_of_window_plus_5, end_utc)
    assert res["status"] == "unavailable"
    assert res["valid_hours"] == 5
    assert res["value"] is None

    # 2-hour timestamp gaps spanning 14h -> only 4 points land inside [T-7h, T]
    two_hour_gap_series = [
        {"time": (end_utc - timedelta(hours=h)).isoformat(), "o3": 70.0, "is_forecast": False}
        for h in range(14, -1, -2)
    ]
    res_gaps = compute_rolling_8h_ozone(two_hour_gap_series, end_utc)
    assert res_gaps["status"] == "unavailable"
    assert res_gaps["valid_hours"] == 4
    assert res_gaps["value"] is None


def test_rolling_8h_o3_preserves_zero_and_rejects_nan_inf_bool_negative():
    end_utc = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)

    # All-zero 8 hours preserves 0.0
    zeros_series = [
        {"time": (end_utc - timedelta(hours=h)).isoformat(), "o3": 0.0, "is_forecast": False}
        for h in range(7, -1, -1)
    ]
    res_zero = compute_rolling_8h_ozone(zeros_series, end_utc)
    assert res_zero["status"] == "available"
    assert res_zero["valid_hours"] == 8
    assert res_zero["value"] == 0.0

    # Mixed invalid values (NaN, inf, -inf, True, -5.0, None) must NOT count toward valid_hours
    mixed_invalid = [
        {"time": (end_utc - timedelta(hours=7)).isoformat(), "o3": 0.0, "is_forecast": False},
        {"time": (end_utc - timedelta(hours=6)).isoformat(), "o3": 20.0, "is_forecast": False},
        {"time": (end_utc - timedelta(hours=5)).isoformat(), "o3": float("nan"), "is_forecast": False},
        {"time": (end_utc - timedelta(hours=4)).isoformat(), "o3": float("inf"), "is_forecast": False},
        {"time": (end_utc - timedelta(hours=3)).isoformat(), "o3": float("-inf"), "is_forecast": False},
        {"time": (end_utc - timedelta(hours=2)).isoformat(), "o3": True, "is_forecast": False},
        {"time": (end_utc - timedelta(hours=1)).isoformat(), "o3": -5.0, "is_forecast": False},
        {"time": end_utc.isoformat(), "o3": None, "is_forecast": False},
    ]
    res_invalid = compute_rolling_8h_ozone(mixed_invalid, end_utc)
    assert res_invalid["status"] == "unavailable"
    assert res_invalid["valid_hours"] == 2
    assert res_invalid["value"] is None


@pytest.mark.asyncio
async def test_no_fallback_to_instantaneous_o3_or_synthesized_diurnal_series():
    provider = OpenMeteoAirQualityProvider()
    # Only 3 valid hourly points exist despite high instantaneous current.ozone=210.0
    times = ["2026-11-27T13:00Z", "2026-11-27T14:00Z", "2026-11-27T15:00Z"]
    payload = _build_open_meteo_payload(
        current_time="2026-11-27T15:00Z",
        hourly_times=times,
        hourly_o3=[40.0, 50.0, 60.0],
        current_o3=210.0,
    )

    with patch("httpx.AsyncClient.get", _mock_httpx_get(payload)):
        meteo_data = await provider.get_current_air_quality(28.6139, 77.2090)

    assert meteo_data is not None
    assert meteo_data["rolling_o3_8h"]["status"] == "unavailable"
    assert meteo_data["rolling_o3_8h"]["value"] is None
    assert meteo_data["rolling_o3_8h"]["valid_hours"] == 3

    # Even when hourly_series is empty and manager triggers _synthesize_diurnal_series for charts,
    # synthesized data must NEVER populate rolling_o3_8h.
    empty_hourly_meteo = {**meteo_data, "hourly_series": [], "rolling_o3_8h": None}
    manager = EnvironmentalDataManager()
    with (
        patch("app.services.providers.manager.openaq_provider.get_current_air_quality", new=AsyncMock(return_value=None)),
        patch("app.services.providers.manager.waqi_provider.get_current_air_quality", new=AsyncMock(return_value=None)),
        patch("app.services.providers.manager.open_meteo_provider.get_current_air_quality", new=AsyncMock(return_value=empty_hourly_meteo)),
    ):
        unified = await manager.get_unified_air_quality(28.6139, 77.2090, "Delhi")

    # Chart history is populated via _synthesize_diurnal_series, while 8h rolling O3 stays unavailable
    assert len(unified.hourly_history or []) > 0
    assert unified.model_derived_aggregates is not None
    o3_8h = unified.model_derived_aggregates["o3_8h"]
    assert o3_8h["status"] == "unavailable"
    assert o3_8h["value"] is None
    assert o3_8h["data_origin"] == "model_derived"
    assert o3_8h["is_regulatory_observation"] is False
