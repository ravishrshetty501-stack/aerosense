from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.providers.base import AirQualityResponse, NormalizedMeasurement
from app.services.providers.manager import EnvironmentalDataManager
from app.services.providers.open_meteo import OpenMeteoAirQualityProvider
from app.services.providers.openaq import OpenAQProvider
from app.services.providers.waqi import WAQIProvider


def _mock_http_response(status_code: int, payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


@pytest.mark.asyncio
async def test_waqi_keeps_overall_aqi_and_subindices_separate_from_concentrations():
    """WAQI data.aqi and iaqi.<pol>.v must be stored as provider indices with value=None and never enter concentration AQI."""
    waqi = WAQIProvider(api_key="test-waqi-key")
    payload = {
        "status": "ok",
        "data": {
            "aqi": 156,
            "dominentpol": "pm25",
            "city": {"name": "Test Station Alpha"},
            "time": {"iso": "2026-11-27T10:00:00Z"},
            "iaqi": {
                "pm25": {"v": 156},
                "o3": {"v": 120},   # AQI sub-index, NOT 120 ug/m3
                "no2": {"v": 0},    # Genuine 0 sub-index preserved
                "pm10": {"v": "-"}, # Invalid string rejected
                "so2": {"v": True}, # Bool rejected
                "co": {"v": -4},    # Negative rejected
            },
        },
    }

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_http_response(200, payload))):
        waqi_res = await waqi.get_current_air_quality(35.68, 139.69, "Tokyo")

    assert waqi_res is not None
    assert waqi_res["provider_aqi"] == 156.0
    assert waqi_res["dominant_pollutant"] == "pm25"
    assert waqi_res["provider_subindices"] == {"pm25": 156.0, "o3": 120.0, "no2": 0.0}

    o3_meas = waqi_res["measurements"]["o3"]
    assert o3_meas.value is None
    assert o3_meas.unit == "aqi_subindex"
    assert o3_meas.original_value == 120.0
    assert o3_meas.original_unit == "waqi_iaqi_subindex"
    assert o3_meas.provider_aqi_subindex == 120.0
    assert o3_meas.data_origin == "provider_index"

    assert waqi_res["measurements"]["no2"].provider_aqi_subindex == 0.0
    assert "pm10" not in waqi_res["measurements"]
    assert "so2" not in waqi_res["measurements"]
    assert "co" not in waqi_res["measurements"]

    # When Open-Meteo is unavailable and only WAQI responds, concentration AQI standards MUST stay Unavailable
    mgr = EnvironmentalDataManager()
    with (
        patch("app.services.providers.manager.open_meteo_provider.get_current_air_quality", new=AsyncMock(return_value=None)),
        patch("app.services.providers.manager.openaq_provider.get_current_air_quality", new=AsyncMock(return_value=None)),
        patch("app.services.providers.manager.waqi_provider.get_current_air_quality", new=AsyncMock(return_value=waqi_res)),
    ):
        unified = await mgr.get_unified_air_quality(35.68, 139.69, "Tokyo", "US_EPA")

    assert isinstance(unified, AirQualityResponse)
    assert unified.aqi_standard_results["US_EPA"]["aqi"] is None
    assert unified.aqi_standard_results["INDIA_CPCB"]["aqi"] is None
    assert unified.aqi_standard_results["EUROPEAN_AQI"]["aqi"] is None
    assert unified.is_ground_observation is False
    assert unified.provider_indices is not None
    assert unified.provider_indices["waqi"]["overall_aqi"] == 156.0
    assert unified.provider_indices["waqi"]["subindices"]["o3"] == 120.0
    assert unified.weather_context["provider_us_aqi"] is None


@pytest.mark.asyncio
async def test_waqi_does_not_erase_valid_open_meteo_concentrations():
    """WAQI provider sub-indices must enrich, not overwrite, valid Open-Meteo model concentrations."""
    now = datetime(2026, 11, 27, 10, 0, tzinfo=timezone.utc)
    meteo_data = {
        "source": "Open-Meteo Air Quality",
        "timezone": "Asia/Tokyo",
        "elevation": 40,
        "provider_us_aqi": 45,
        "provider_european_aqi": 20,
        "measurements": {
            "pm25": NormalizedMeasurement(
                pollutant="pm25",
                value=10.0,
                unit="ug/m3",
                measurement_type="model_estimate",
                source="Open-Meteo CAMS Ensemble",
                data_quality="verified",
                observation_timestamp=now,
                retrieval_timestamp=now,
                original_value=10.0,
                original_unit="μg/m³",
                averaging_period="instantaneous",
                data_origin="model_derived",
                conversion_method="none",
            ),
            "o3": NormalizedMeasurement(
                pollutant="o3",
                value=40.0,
                unit="ug/m3",
                measurement_type="model_estimate",
                source="Open-Meteo CAMS Ensemble",
                data_quality="verified",
                observation_timestamp=now,
                retrieval_timestamp=now,
                original_value=40.0,
                original_unit="μg/m³",
                averaging_period="instantaneous",
                data_origin="model_derived",
                conversion_method="none",
            ),
        },
        "hourly_series": [],
    }
    waqi_data = {
        "source": "WAQI Ground Station (Tokyo Bay)",
        "station_name": "Tokyo Bay",
        "provider_aqi": 99,
        "dominant_pollutant": "pm25",
        "provider_subindices": {"pm25": 99.0},
        "observation_time": now,
        "measurements": {
            "pm25": NormalizedMeasurement(
                pollutant="pm25",
                value=None,
                unit="aqi_subindex",
                measurement_type="ground_observation",
                source="WAQI Ground Station (Tokyo Bay)",
                data_quality="verified",
                observation_timestamp=now,
                retrieval_timestamp=now,
                original_value=99.0,
                original_unit="waqi_iaqi_subindex",
                averaging_period="provider_reported",
                data_origin="provider_index",
                provider_aqi_subindex=99.0,
                conversion_method="none",
            )
        },
    }

    mgr = EnvironmentalDataManager()
    with (
        patch("app.services.providers.manager.open_meteo_provider.get_current_air_quality", new=AsyncMock(return_value=meteo_data)),
        patch("app.services.providers.manager.openaq_provider.get_current_air_quality", new=AsyncMock(return_value=None)),
        patch("app.services.providers.manager.waqi_provider.get_current_air_quality", new=AsyncMock(return_value=waqi_data)),
    ):
        unified = await mgr.get_unified_air_quality(35.68, 139.69, "Tokyo", "US_EPA")

    # Open-Meteo 10.0 ug/m3 concentration preserved (May 2024 EPA -> 53 Moderate; 2012 rule was 42);
    # WAQI 99 sub-index attached without replacing concentration or inflating EPA AQI
    assert unified.measurements["pm25"].value == 10.0
    assert unified.measurements["pm25"].unit == "ug/m3"
    assert unified.measurements["pm25"].data_origin == "model_derived"
    assert unified.measurements["pm25"].provider_aqi_subindex == 99.0
    assert unified.aqi_standard_results["US_EPA"]["aqi"] == 53  # From 10.0 ug/m3 PM2.5 (May 2024), NOT 99!
    assert unified.aqi_standard_results["US_EPA"]["calculation_basis"] == "model_derived_provisional"
    assert unified.provider_indices["waqi"]["overall_aqi"] == 99
    assert unified.provider_indices["open_meteo"]["us_aqi"] == 45
    assert unified.is_ground_observation is False


@pytest.mark.asyncio
async def test_openaq_sensors_id_unit_resolution_conversion_and_rejection():
    """OpenAQ must resolve sensorsId metadata, preserve ppm/ppb without inventing ug/m3, and reject missing/unsupported units."""
    openaq = OpenAQProvider(api_key="test-openaq-key")

    nearby_station = [
        {
            "id": 4242,
            "name": "EPA Reference Site",
            "latitude": 38.89,
            "longitude": -77.03,
            "sensors": [
                {"id": 101, "parameter": {"name": "pm25", "units": "µg/m³"}},
                {"id": 102, "parameter": {"name": "o3", "units": "ppm"}},
                {"id": 103, "parameter": {"name": "no2", "units": "ppb"}},
                {"id": 104, "parameter": {"name": "co", "units": "ug/m3"}},
                {"id": 105, "parameter": {"name": "pm10", "units": "ppm"}},       # Unsupported unit for particulates
                {"id": 106, "parameter": {"name": "so2"}},                        # Missing unit
            ],
        }
    ]
    latest_payload = {
        "results": [
            {"sensorsId": 101, "value": 0.0, "datetime": {"utc": "2026-11-27T10:00:00Z"}},
            {"sensorsId": 102, "value": 0.075, "datetime": {"utc": "2026-11-27T10:00:00Z"}},
            {"sensorsId": 103, "value": 25.0, "datetime": {"utc": "2026-11-27T10:00:00Z"}},
            {"sensorsId": 104, "value": 1500.0, "datetime": {"utc": "2026-11-27T10:00:00Z"}},
            {"sensorsId": 105, "value": 12.0, "datetime": {"utc": "2026-11-27T10:00:00Z"}},
            {"sensorsId": 106, "value": 30.0, "datetime": {"utc": "2026-11-27T10:00:00Z"}},
            # Invalid non-finite / negative / bool entries
            {"sensorsId": 101, "value": float("nan")},
        ]
    }

    with (
        patch.object(openaq, "find_nearby_stations", new=AsyncMock(return_value=nearby_station)),
        patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_http_response(200, latest_payload))),
    ):
        res = await openaq.get_current_air_quality(38.89, -77.03, "Washington")

    assert res is not None
    meas = res["measurements"]

    # 1. PM2.5 in ug/m3 with genuine 0 preserved
    assert meas["pm25"].value == 0.0
    assert meas["pm25"].unit == "ug/m3"
    assert meas["pm25"].original_value == 0.0
    assert meas["pm25"].original_unit == "µg/m³"
    assert meas["pm25"].data_origin == "measured"
    assert meas["pm25"].averaging_period == "unknown"

    # 2. CO in ug/m3 converted cleanly to mg/m3 (SI scaling) with traceability
    assert meas["co"].value == 1.5
    assert meas["co"].unit == "mg/m3"
    assert meas["co"].original_value == 1500.0
    assert meas["co"].original_unit == "ug/m3"
    assert meas["co"].conversion_method == "ugm3_to_mgm3"

    # 3. O3 in ppm & NO2 in ppb NOT silently interpreted as ug/m3
    assert meas["o3"].value is None
    assert meas["o3"].unit == "ppm"
    assert meas["o3"].original_value == 0.075
    assert meas["o3"].original_unit == "ppm"
    assert "temperature and pressure" in (meas["o3"].conversion_assumption or "").lower()

    assert meas["no2"].value is None
    assert meas["no2"].unit == "ppb"
    assert meas["no2"].original_value == 25.0
    assert meas["no2"].original_unit == "ppb"

    # 4. Particulate in ppm & missing unit marked unavailable
    assert meas["pm10"].value is None
    assert meas["pm10"].measurement_type == "unavailable"
    assert meas["pm10"].data_origin == "unavailable"
    assert meas["pm10"].original_value == 12.0
    assert meas["pm10"].original_unit == "ppm"

    assert meas["so2"].value is None
    assert meas["so2"].unit == "unavailable"
    assert meas["so2"].measurement_type == "unavailable"
    assert meas["so2"].original_value == 30.0
    assert meas["so2"].original_unit is None

    # 5. Feeding OpenAQ-only result into manager excludes ppm/ppb/unavailable from AQI calculations
    mgr = EnvironmentalDataManager()
    only_unconverted = {
        **res,
        "measurements": {"o3": meas["o3"], "pm10": meas["pm10"], "so2": meas["so2"]},
    }
    with (
        patch("app.services.providers.manager.open_meteo_provider.get_current_air_quality", new=AsyncMock(return_value=None)),
        patch("app.services.providers.manager.openaq_provider.get_current_air_quality", new=AsyncMock(return_value=only_unconverted)),
    ):
        unified = await mgr.get_unified_air_quality(38.89, -77.03, "Washington", "US_EPA")

    assert unified.aqi_standard_results["US_EPA"]["aqi"] is None
    assert unified.aqi_standard_results["US_EPA"]["category"] == "Unavailable"
    assert unified.measurements["o3"].original_value == 0.075
    assert unified.measurements["o3"].original_unit == "ppm"


@pytest.mark.asyncio
async def test_open_meteo_marks_model_derived_and_handles_zero_and_non_finite():
    """Open-Meteo must tag measurements as model_derived/instantaneous, preserve 0.0, and reject non-finite values."""
    provider = OpenMeteoAirQualityProvider()
    payload = {
        "elevation": 12.0,
        "timezone": "UTC",
        "current": {
            "time": "2026-11-27T10:00",
            "pm2_5": 0.0,
            "pm10": float("nan"),
            "nitrogen_dioxide": -3.0,
            "sulphur_dioxide": float("inf"),
            "ozone": 85.4,
            "carbon_monoxide": 500.0,
            "us_aqi": 35,
            "european_aqi": 20,
        },
        "current_units": {
            "pm2_5": "μg/m³",
            "pm10": "μg/m³",
            "nitrogen_dioxide": "μg/m³",
            "sulphur_dioxide": "μg/m³",
            "ozone": "μg/m³",
            "carbon_monoxide": "μg/m³",
        },
        "hourly": {
            "time": ["2026-11-27T10:00"],
            "pm2_5": [0.0],
            "pm10": [None],
            "nitrogen_dioxide": [None],
            "ozone": [85.4],
            "us_aqi": [35],
        },
    }

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_http_response(200, payload))):
        res = await provider.get_current_air_quality(0.0, 0.0, "ZeroPoint")

    assert res is not None
    pm25 = res["measurements"]["pm25"]
    assert pm25.value == 0.0
    assert pm25.unit == "ug/m3"
    assert pm25.original_value == 0.0
    assert pm25.original_unit == "μg/m³"
    assert pm25.data_origin == "model_derived"
    assert pm25.averaging_period == "instantaneous"

    o3 = res["measurements"]["o3"]
    assert o3.value == 85.4
    assert o3.data_origin == "model_derived"
    assert o3.averaging_period == "instantaneous"

    co = res["measurements"]["co"]
    assert co.value == 0.5
    assert co.unit == "mg/m3"
    assert co.original_value == 500.0
    assert co.original_unit == "μg/m³"
    assert co.conversion_method == "ugm3_to_mgm3"

    assert "pm10" not in res["measurements"]
    assert "no2" not in res["measurements"]
    assert "so2" not in res["measurements"]


@pytest.mark.asyncio
async def test_api_air_quality_current_contract_remains_compatible(monkeypatch):
    """ASGI /api/v1/air-quality/current preserves existing JSON contract while exposing additive provenance."""
    now = datetime(2026, 11, 27, 10, 0, tzinfo=timezone.utc)
    mock_resp = AirQualityResponse(
        location={"name": "Tokyo", "city": "Tokyo", "latitude": 35.68, "longitude": 139.69, "timezone": "UTC"},
        measurements={
            "pm25": NormalizedMeasurement(
                pollutant="pm25",
                value=12.0,
                unit="ug/m3",
                measurement_type="model_estimate",
                source="Open-Meteo CAMS Ensemble",
                data_quality="verified",
                observation_timestamp=now,
                retrieval_timestamp=now,
                original_value=12.0,
                original_unit="μg/m³",
                averaging_period="instantaneous",
                data_origin="model_derived",
                conversion_method="none",
            )
        },
        aqi_standard_results={
            "US_EPA": {"standard": "US_EPA", "aqi": 50, "category": "Good", "dominant_pollutant": "PM25", "color": "#10b981", "subindices": {"pm25": 50}, "advisory": "Good.", "is_reliable": True}
        },
        dominant_pollutant="PM25",
        weather_context={"elevation": 40, "provider_us_aqi": 50, "provider_european_aqi": 20},
        provider_indices={"waqi": {"overall_aqi": 52, "subindices": {"pm25": 52}}},
        hourly_history=[],
        forecast=[],
        primary_source="Open-Meteo CAMS Ensemble",
        data_freshness_minutes=5,
        is_ground_observation=False,
    )

    from app.services.providers import manager as manager_mod
    monkeypatch.setattr(manager_mod.data_manager, "get_unified_air_quality", AsyncMock(return_value=mock_resp))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/air-quality/current?lat=35.68&lon=139.69&city=Tokyo&standard=US_EPA")

    assert resp.status_code == 200
    body = resp.json()
    assert body["location"]["name"] == "Tokyo"
    assert body["aqi_standard_results"]["US_EPA"]["aqi"] == 50
    assert body["measurements"]["pm25"]["value"] == 12.0
    assert body["measurements"]["pm25"]["data_origin"] == "model_derived"
    assert body["provider_indices"]["waqi"]["overall_aqi"] == 52


@pytest.mark.asyncio
async def test_openaq_preserves_usable_sensor_on_duplicate_null_and_open_meteo_rejects_bad_coords():
    from app.services.providers.open_meteo import OpenMeteoAirQualityProvider

    om = OpenMeteoAirQualityProvider()
    assert await om.get_current_air_quality(95.0, 10.0, "Bad") is None
    assert await om.get_current_air_quality(float("nan"), 10.0, "NaN") is None

    oaq = OpenAQProvider(api_key="test-key")
    assert await oaq.find_nearby_stations(-91.0, 0.0) == []

    loc_payload = {
        "results": [
            {
                "id": 999,
                "name": "Dual Sensor Station",
                "coordinates": {"latitude": 28.6, "longitude": 77.2},
                "sensors": [
                    {"id": 1, "parameter": {"name": "pm25", "units": "µg/m³"}, "period": {"label": "24h"}},
                    {"id": 2, "parameter": {"name": "pm25", "units": "ppm"}, "period": {"label": "1h"}},
                ],
            }
        ]
    }
    latest_payload = {
        "results": [
            {"sensorsId": 1, "value": 85.0, "datetime": {"utc": "2026-11-27T10:00:00Z"}},
            {"sensorsId": 2, "value": 0.1, "datetime": {"utc": "2026-11-27T10:00:00Z"}},
        ]
    }
    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(side_effect=[_mock_http_response(200, loc_payload), _mock_http_response(200, latest_payload)]),
    ):
        oaq_res = await oaq.get_current_air_quality(28.6, 77.2, "Delhi")

    assert oaq_res is not None
    assert oaq_res["measurements"]["pm25"].value == 85.0
    assert oaq_res["measurements"]["pm25"].unit == "ug/m3"
