from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.aqi.us_epa import (
    EPA_METHODOLOGY_VERSION,
    calculate_epa_ozone_subindex,
    calculate_epa_subindex,
    calculate_us_epa_aqi,
    classify_epa_measurement_eligibility,
)
from app.services.providers.base import NormalizedMeasurement
from app.services.providers.manager import EnvironmentalDataManager


@pytest.mark.parametrize(
    ("conc", "expected"),
    [
        (0.0, 0),
        (9.0, 50),
        (9.09, 50),
        (9.1, 51),
        (12.0, 56),   # May 2024 update (was 50 under 2012 rule)
        (35.4, 100),
        (35.49, 100),
        (35.5, 101),
        (55.4, 150),
        (55.5, 151),
        (125.4, 200),
        (125.5, 201),
        (225.4, 300),
        (225.5, 301),
        (325.4, 500),
        (400.0, 649),  # Beyond 500 extrapolation via Equation 1
    ],
)
def test_pm25_may_2024_all_boundaries_and_extrapolation(conc: float, expected: int):
    assert calculate_epa_subindex("pm25", conc) == expected


@pytest.mark.parametrize(
    ("conc", "expected"),
    [
        (0, 0),
        (54, 50),
        (54.9, 50),
        (55, 51),
        (154, 100),
        (155, 101),
        (254, 150),
        (255, 151),
        (354, 200),
        (355, 201),
        (424, 300),
        (425, 301),
        (504, 400),
        (505, 401),
        (604, 500),
        (704, 600),  # Extrapolated above 500
    ],
)
def test_pm10_boundaries_truncation_and_above_500(conc: float, expected: int):
    assert calculate_epa_subindex("pm10", conc) == expected


@pytest.mark.parametrize(
    ("conc", "expected"),
    [
        (0.000, 0),
        (0.054, 50),
        (0.0549, 50),
        (0.055, 51),
        (0.070, 100),
        (0.0709, 100),
        (0.071, 101),
        (0.085, 150),
        (0.086, 151),
        (0.105, 200),
        (0.106, 201),
        (0.200, 300),
        (0.201, None),  # 8-hr O3 does not define >= 301
    ],
)
def test_ozone_8h_boundaries_truncation_and_upper_cutoff(conc: float, expected: int | None):
    assert calculate_epa_ozone_subindex(conc, unit="ppm", averaging_period="8h") == expected


@pytest.mark.parametrize(
    ("conc", "allow_alt", "expected"),
    [
        (0.124, True, None),   # 1-hr O3 does not define AQI 0-100
        (0.125, False, None),  # 101-300 disabled unless precautionary policy opted in
        (0.125, True, 101),
        (0.164, True, 150),
        (0.165, True, 151),
        (0.204, True, 200),
        (0.205, True, 201),
        (0.404, True, 300),
        (0.404, False, None),
        (0.405, False, 301),   # >= 301 uses 1-hr O3 even without precautionary alt
        (0.504, False, 400),
        (0.505, False, 401),
        (0.604, False, 500),
        (0.704, False, 600),   # Extrapolated above 500
    ],
)
def test_ozone_1h_boundaries_selection_and_above_500(conc: float, allow_alt: bool, expected: int | None):
    assert (
        calculate_epa_ozone_subindex(
            conc,
            unit="ppm",
            averaging_period="1h",
            allow_1hr_precautionary_alternative=allow_alt,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("pollutant", "conc", "unit", "period", "expected"),
    [
        # CO (ppm, 8-hr, truncated to 0.1)
        ("co", 0.0, "ppm", "8h", 0),
        ("co", 4.4, "ppm", "8h", 50),
        ("co", 4.49, "ppm", "8h", 50),
        ("co", 4.5, "ppm", "8h", 51),
        ("co", 9.4, "ppm", "8h", 100),
        ("co", 12.4, "ppm", "8h", 150),
        ("co", 15.4, "ppm", "8h", 200),
        ("co", 30.4, "ppm", "8h", 300),
        ("co", 40.4, "ppm", "8h", 400),
        ("co", 50.4, "ppm", "8h", 500),
        ("co", 60.4, "ppm", "8h", 600),
        # NO2 (ppb, 1-hr, truncated to integer)
        ("no2", 0, "ppb", "1h", 0),
        ("no2", 53.9, "ppb", "1h", 50),
        ("no2", 54, "ppb", "1h", 51),
        ("no2", 100, "ppb", "1h", 100),
        ("no2", 360, "ppb", "1h", 150),
        ("no2", 649, "ppb", "1h", 200),
        ("no2", 1249, "ppb", "1h", 300),
        ("no2", 1649, "ppb", "1h", 400),
        ("no2", 2049, "ppb", "1h", 500),
        ("no2", 2449, "ppb", "1h", 599),
        # SO2 1-hr (0-200 only) and 24-hr (201-500+)
        ("so2", 0, "ppb", "1h", 0),
        ("so2", 35, "ppb", "1h", 50),
        ("so2", 75, "ppb", "1h", 100),
        ("so2", 185, "ppb", "1h", 150),
        ("so2", 304, "ppb", "1h", 200),
        ("so2", 305, "ppb", "1h", None),
        ("so2", 304, "ppb", "24h", None),
        ("so2", 305, "ppb", "24h", 201),
        ("so2", 604, "ppb", "24h", 300),
        ("so2", 804, "ppb", "24h", 400),
        ("so2", 1004, "ppb", "24h", 500),
        ("so2", 1204, "ppb", "24h", 599),
    ],
)
def test_co_no2_so2_native_units_periods_and_above_500(
    pollutant: str,
    conc: float,
    unit: str,
    period: str,
    expected: int | None,
):
    assert calculate_epa_subindex(pollutant, conc, unit=unit, averaging_period=period) == expected


def test_exact_half_integer_rounding_half_up():
    """EPA Equation 1 rounds half-integers up (ROUND_HALF_UP), not Python banker's round()."""
    # CO 1.1 ppm in (0.0, 4.4, 0, 50) -> (50 / 4.4) * 1.1 = 12.5 exactly -> 13 (Python round(12.5) == 12)
    assert calculate_epa_subindex("co", 1.1, unit="ppm", averaging_period="8h") == 13
    # CO 3.3 ppm -> (50 / 4.4) * 3.3 = 37.5 -> 38
    assert calculate_epa_subindex("co", 3.3, unit="ppm", averaging_period="8h") == 38


def test_native_si_volumetric_scaling_without_stp_mass_conversion():
    # Pure metric volumetric ratio (1 ppm = 1000 ppb)
    assert calculate_epa_subindex("o3", 70.9, unit="ppb", averaging_period="8h") == 100  # 0.070 ppm
    assert calculate_epa_subindex("no2", 0.100, unit="ppm", averaging_period="1h") == 100  # 100 ppb
    assert calculate_epa_subindex("so2", 0.075, unit="ppm", averaging_period="1h") == 100  # 75 ppb
    assert calculate_epa_subindex("co", 4400.0, unit="ppb", averaging_period="8h") == 50  # 4.4 ppm

    # Mass units (ug/m3 / mg/m3) MUST NEVER be silently STP-converted for EPA gases
    assert calculate_epa_subindex("o3", 100.0, unit="ug/m3", averaging_period="8h") is None
    assert calculate_epa_subindex("co", 5.0, unit="mg/m3", averaging_period="8h") is None
    assert calculate_epa_subindex("no2", 100.0, unit="ug/m3", averaging_period="1h") is None
    assert calculate_epa_subindex("so2", 75.0, unit="ug/m3", averaging_period="1h") is None


def test_metadata_free_and_instantaneous_ozone_rejection():
    # Metadata-free scalar ozone rejected
    assert calculate_epa_subindex("o3", 0.070) is None
    assert calculate_epa_subindex("o3", 0.070, unit="ppm") is None
    assert calculate_epa_subindex("o3", 0.070, averaging_period="8h") is None

    # Instantaneous or unknown averaging period rejected
    assert calculate_epa_subindex("o3", 0.070, unit="ppm", averaging_period="instantaneous") is None
    assert calculate_epa_subindex("o3", 0.070, unit="ppm", averaging_period="unknown") is None

    res_bare = calculate_us_epa_aqi({"o3": 0.070})
    assert res_bare["aqi"] is None
    assert res_bare["is_reliable"] is False
    assert res_bare["calculation_basis"] == "unavailable"
    assert res_bare["pollutant_provenance"]["o3"]["classification"] == "unavailable_or_insufficient"

    res_inst = calculate_us_epa_aqi(
        {},
        measurement_metadata={
            "o3": {
                "value": 0.095,
                "unit": "ppm",
                "averaging_period": "instantaneous",
                "data_origin": "measured",
            }
        },
    )
    assert res_inst["aqi"] is None
    assert "o3" not in res_inst["subindices"]
    assert res_inst["pollutant_provenance"]["o3"]["classification"] == "unavailable_or_insufficient"


def test_ozone_8h_vs_1h_policy_selection():
    # Both 8h (100) and 1h (150) within 101-300: default policy disabled -> keeps 8h (100)
    both_mid = {
        "o3_8h": {"value": 0.070, "unit": "ppm", "averaging_period": "8h", "data_origin": "measured"},
        "o3_1h": {"value": 0.164, "unit": "ppm", "averaging_period": "1h", "data_origin": "measured"},
    }
    res_default = calculate_us_epa_aqi({}, measurement_metadata=both_mid)
    assert res_default["aqi"] == 100
    assert res_default["ozone_selection_basis"] == "o3_8h_standard"

    # Explicit precautionary alternative enabled -> max(8h=100, 1h=150) = 150
    res_alt = calculate_us_epa_aqi(
        {},
        measurement_metadata=both_mid,
        allow_1hr_precautionary_alternative=True,
    )
    assert res_alt["aqi"] == 150
    assert res_alt["ozone_selection_basis"] == "o3_1h_precautionary_alternative"

    # When 1h reaches >= 301 (0.405 ppm), mandatory 1h applies even with default policy=False
    high_1h = {
        "o3_8h": {"value": 0.210, "unit": "ppm", "averaging_period": "8h", "data_origin": "measured"},  # >0.200 undefined for 8h
        "o3_1h": {"value": 0.405, "unit": "ppm", "averaging_period": "1h", "data_origin": "measured"},  # 301
    }
    res_high = calculate_us_epa_aqi({}, measurement_metadata=high_1h)
    assert res_high["aqi"] == 301
    assert res_high["ozone_selection_basis"] == "o3_1h_mandatory_above_300"


def test_eligibility_provenance_four_buckets_and_no_compliance_claim():
    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    meta = {
        # 1. Regulatory-eligible measured native ppb NO2 (100 ppb -> AQI 100)
        "no2": NormalizedMeasurement(
            pollutant="no2",
            value=None,
            unit="ppb",
            measurement_type="ground_observation",
            source="OpenAQ / Station 1",
            data_quality="verified",
            observation_timestamp=now,
            retrieval_timestamp=now,
            original_value=100.0,
            original_unit="ppb",
            averaging_period="1h",
            data_origin="measured",
        ),
        # 2. Model-derived provisional particulate (15.0 ug/m3 PM2.5)
        "pm25": NormalizedMeasurement(
            pollutant="pm25",
            value=15.0,
            unit="ug/m3",
            measurement_type="model_estimate",
            source="Open-Meteo CAMS Ensemble",
            data_quality="verified",
            observation_timestamp=now,
            retrieval_timestamp=now,
            original_value=15.0,
            original_unit="ug/m3",
            averaging_period="instantaneous",
            data_origin="model_derived",
        ),
        # 3. Provider-reported index (WAQI)
        "pm10": NormalizedMeasurement(
            pollutant="pm10",
            value=None,
            unit="aqi_subindex",
            measurement_type="ground_observation",
            source="WAQI",
            data_quality="verified",
            observation_timestamp=now,
            retrieval_timestamp=now,
            original_value=220.0,
            original_unit="waqi_iaqi_subindex",
            averaging_period="provider_reported",
            data_origin="provider_index",
            provider_aqi_subindex=220.0,
        ),
        # 4. Unavailable / insufficiently specified O3 (unknown averaging period)
        "o3": NormalizedMeasurement(
            pollutant="o3",
            value=None,
            unit="ppm",
            measurement_type="ground_observation",
            source="OpenAQ / Station 1",
            data_quality="provisional",
            observation_timestamp=now,
            retrieval_timestamp=now,
            original_value=0.075,
            original_unit="ppm",
            averaging_period="unknown",
            data_origin="measured",
        ),
    }

    rolling_o3_8h = {
        "status": "available",
        "value": 92.4,
        "unit": "ug/m3",
        "averaging_period": "8h",
        "valid_hours": 8,
        "expected_hours": 8,
        "completeness_ratio": 1.0,
        "completeness_policy": "model_derived_6_of_8_completeness",
        "data_origin": "model_derived",
        "is_regulatory_observation": False,
    }

    res = calculate_us_epa_aqi(
        {},
        measurement_metadata=meta,
        model_derived_aggregates={"o3_8h": rolling_o3_8h},
    )
    assert res["methodology_version"] == EPA_METHODOLOGY_VERSION
    assert res["is_regulatory_compliant"] is False
    assert res["calculation_basis"] == "regulatory_eligible"
    assert res["aqi"] == 100
    assert res["dominant_pollutant"] == "NO2"
    assert res["pollutant_provenance"]["no2"]["classification"] == "regulatory_eligible"
    assert res["pollutant_provenance"]["pm25"]["classification"] == "model_derived_provisional"
    assert res["pollutant_provenance"]["pm10"]["classification"] == "provider_index"
    assert res["pollutant_provenance"]["o3"]["classification"] == "unavailable_or_insufficient"
    assert res["provisional_estimates"]["o3_8h"]["value"] == 92.4
    assert res["provisional_estimates"]["o3_8h"]["is_regulatory_observation"] is False
    assert res["provisional_estimates"]["o3_8h"]["epa_subindex"] is None
    assert "o3" not in res["subindices"]
    assert "pm10" not in res["subindices"]


def test_zero_missing_bool_negative_and_nonfinite_inputs():
    assert calculate_epa_subindex("pm25", 0.0) == 0
    assert calculate_epa_subindex("co", 0.0, unit="ppm", averaging_period="8h") == 0
    assert calculate_epa_ozone_subindex(0.0, unit="ppm", averaging_period="8h") == 0

    for bad in [None, True, False, -0.001, float("nan"), float("inf"), float("-inf"), "0.05"]:
        assert calculate_epa_subindex("pm25", bad) is None
        assert calculate_epa_ozone_subindex(bad, unit="ppm", averaging_period="8h") is None
        info = classify_epa_measurement_eligibility("o3", {"value": bad, "unit": "ppm", "averaging_period": "8h", "data_origin": "measured"})
        assert info["classification"] == "unavailable_or_insufficient"


@pytest.mark.asyncio
async def test_api_and_frontend_contract_compatibility_end_to_end():
    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    openaq_data = {
        "source": "OpenAQ Ground Station: EPA Ref Site",
        "station_id": 1001,
        "station_name": "EPA Ref Site",
        "latitude": 38.89,
        "longitude": -77.03,
        "is_ground_observation": True,
        "measurements": {
            "o3": NormalizedMeasurement(
                pollutant="o3",
                value=None,
                unit="ppm",
                measurement_type="ground_observation",
                source="OpenAQ / EPA Ref Site",
                data_quality="verified",
                observation_timestamp=now,
                retrieval_timestamp=now,
                original_value=0.070,
                original_unit="ppm",
                averaging_period="8h",
                data_origin="measured",
            ),
            "pm25": NormalizedMeasurement(
                pollutant="pm25",
                value=9.0,
                unit="ug/m3",
                measurement_type="ground_observation",
                source="OpenAQ / EPA Ref Site",
                data_quality="verified",
                observation_timestamp=now,
                retrieval_timestamp=now,
                original_value=9.0,
                original_unit="µg/m³",
                averaging_period="24h",
                data_origin="measured",
            ),
        },
    }
    meteo_data = {
        "source": "Open-Meteo Air Quality",
        "timezone": "UTC",
        "elevation": 10,
        "observation_time": now,
        "rolling_o3_8h": {
            "status": "available",
            "value": 88.0,
            "unit": "ug/m3",
            "averaging_period": "8h",
            "valid_hours": 8,
            "expected_hours": 8,
            "completeness_ratio": 1.0,
            "completeness_policy": "model_derived_6_of_8_completeness",
            "data_origin": "model_derived",
            "is_regulatory_observation": False,
        },
        "measurements": {},
        "hourly_series": [],
    }

    mgr = EnvironmentalDataManager()
    with (
        patch("app.services.providers.manager.open_meteo_provider.get_current_air_quality", new=AsyncMock(return_value=meteo_data)),
        patch("app.services.providers.manager.openaq_provider.get_current_air_quality", new=AsyncMock(return_value=openaq_data)),
        patch("app.services.providers.manager.waqi_provider.get_current_air_quality", new=AsyncMock(return_value=None)),
    ):
        unified = await mgr.get_unified_air_quality(38.89, -77.03, "Washington", "US_EPA")

    epa_res = unified.aqi_standard_results["US_EPA"]
    # Frontend AQIStandardResult required contract keys
    for key in ("standard", "aqi", "category", "dominant_pollutant", "color", "subindices", "advisory", "is_reliable"):
        assert key in epa_res
    assert epa_res["aqi"] == 100  # 0.070 ppm 8h O3 -> 100 beats 9.0 ug/m3 PM2.5 -> 50
    assert epa_res["dominant_pollutant"] == "O3"
    assert epa_res["is_regulatory_compliant"] is False
    assert epa_res["provisional_estimates"]["o3_8h"]["value"] == 88.0

    # HTTP /api/v1/aqi/calculate backward compatibility
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_pm = await client.post("/api/v1/aqi/calculate?standard=US_EPA", json={"pm25": 9.0})
        assert resp_pm.status_code == 200
        assert resp_pm.json()["aqi"] == 50

        # Metadata-free O3 rejected even over /api/v1/aqi/calculate
        resp_o3 = await client.post("/api/v1/aqi/calculate?standard=US_EPA", json={"o3": 0.070})
        assert resp_o3.status_code == 200
        assert resp_o3.json()["aqi"] is None
