from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.aqi.india_cpcb import (
    CPCB_BREAKPOINTS,
    CPCB_METHODOLOGY_VERSION,
    calculate_cpcb_subindex,
    calculate_india_cpcb_aqi,
    classify_cpcb_measurement_eligibility,
)
from app.services.providers.base import NormalizedMeasurement
from app.services.providers.manager import EnvironmentalDataManager


@pytest.mark.parametrize(
    ("pollutant", "conc", "unit", "period", "expected"),
    [
        # PM2.5 (ug/m3, 24h)
        ("pm25", 0, "ug/m3", "24h", 0),
        ("pm25", 30, "ug/m3", "24h", 50),
        ("pm25", 31, "ug/m3", "24h", 51),
        ("pm25", 60, "ug/m3", "24h", 100),
        ("pm25", 90, "ug/m3", "24h", 200),
        ("pm25", 120, "ug/m3", "24h", 300),
        ("pm25", 250, "ug/m3", "24h", 400),
        ("pm25", 251, "ug/m3", "24h", 401),
        ("pm25", 380, "ug/m3", "24h", 500),
        ("pm25", 900, "ug/m3", "24h", 500),
        # PM10 (ug/m3, 24h)
        ("pm10", 0, "ug/m3", "24h", 0),
        ("pm10", 50, "ug/m3", "24h", 50),
        ("pm10", 100, "ug/m3", "24h", 100),
        ("pm10", 250, "ug/m3", "24h", 200),
        ("pm10", 350, "ug/m3", "24h", 300),
        ("pm10", 430, "ug/m3", "24h", 400),
        ("pm10", 431, "ug/m3", "24h", 401),
        ("pm10", 510, "ug/m3", "24h", 500),
        ("pm10", 1200, "ug/m3", "24h", 500),
        # NO2 (ug/m3, 24h)
        ("no2", 0, "ug/m3", "24h", 0),
        ("no2", 40, "ug/m3", "24h", 50),
        ("no2", 80, "ug/m3", "24h", 100),
        ("no2", 180, "ug/m3", "24h", 200),
        ("no2", 280, "ug/m3", "24h", 300),
        ("no2", 400, "ug/m3", "24h", 400),
        ("no2", 401, "ug/m3", "24h", 401),
        ("no2", 520, "ug/m3", "24h", 500),
        # SO2 (ug/m3, 24h)
        ("so2", 0, "ug/m3", "24h", 0),
        ("so2", 40, "ug/m3", "24h", 50),
        ("so2", 80, "ug/m3", "24h", 100),
        ("so2", 380, "ug/m3", "24h", 200),
        ("so2", 800, "ug/m3", "24h", 300),
        ("so2", 1600, "ug/m3", "24h", 400),
        ("so2", 1601, "ug/m3", "24h", 401),
        ("so2", 2400, "ug/m3", "24h", 500),
        # CO (mg/m3, 8h)
        ("co", 0.0, "mg/m3", "8h", 0),
        ("co", 1.0, "mg/m3", "8h", 50),
        ("co", 2.0, "mg/m3", "8h", 100),
        ("co", 10.0, "mg/m3", "8h", 200),
        ("co", 17.0, "mg/m3", "8h", 300),
        ("co", 34.0, "mg/m3", "8h", 400),
        ("co", 34.1, "mg/m3", "8h", 401),
        ("co", 51.0, "mg/m3", "8h", 500),
        # O3 (ug/m3: 8h up to 208; >208 switches to 1h)
        ("o3", 0, "ug/m3", "8h", 0),
        ("o3", 50, "ug/m3", "8h", 50),
        ("o3", 100, "ug/m3", "8h", 100),
        ("o3", 168, "ug/m3", "8h", 200),
        ("o3", 208, "ug/m3", "8h", 300),
        ("o3", 209, "ug/m3", "8h", None),
        ("o3", 748, "ug/m3", "1h", 400),
        ("o3", 749, "ug/m3", "1h", 401),
        ("o3", 1288, "ug/m3", "1h", 500),
        # NH3 (ug/m3, 24h)
        ("nh3", 0, "ug/m3", "24h", 0),
        ("nh3", 200, "ug/m3", "24h", 50),
        ("nh3", 400, "ug/m3", "24h", 100),
        ("nh3", 800, "ug/m3", "24h", 200),
        ("nh3", 1200, "ug/m3", "24h", 300),
        ("nh3", 1800, "ug/m3", "24h", 400),
        ("nh3", 1801, "ug/m3", "24h", 401),
        ("nh3", 2400, "ug/m3", "24h", 500),
        # Pb (ug/m3, 24h)
        ("pb", 0.0, "ug/m3", "24h", 0),
        ("pb", 0.5, "ug/m3", "24h", 50),
        ("pb", 0.6, "ug/m3", "24h", 51),
        ("pb", 1.0, "ug/m3", "24h", 100),
        ("pb", 2.0, "ug/m3", "24h", 200),
        ("pb", 3.0, "ug/m3", "24h", 300),
        ("pb", 3.5, "ug/m3", "24h", 400),
        ("pb", 3.6, "ug/m3", "24h", 420),
        ("pb", 4.0, "ug/m3", "24h", 500),
        ("pb", 10.0, "ug/m3", "24h", 500),
    ],
)
def test_cpcb_all_eight_pollutant_breakpoints_and_severe_upper_scale(
    pollutant: str,
    conc: float,
    unit: str,
    period: str,
    expected: int,
):
    assert calculate_cpcb_subindex(pollutant, conc, unit=unit, averaging_period=period) == expected


def test_cpcb_severe_tables_are_open_ended_without_invented_ceilings():
    for pollutant in ("pm25", "pm10", "no2", "so2", "co", "o3", "nh3", "pb"):
        severe_row = CPCB_BREAKPOINTS[pollutant][-1]
        assert severe_row[1] is None
        assert severe_row[2] == 401
        assert severe_row[3] == 500
    # Extreme values always stay capped cleanly on CPCB 0-500 scale
    assert calculate_cpcb_subindex("pm25", 10000.0) == 500
    assert calculate_cpcb_subindex("so2", 10000.0) == 500


def test_cpcb_concentration_truncation_and_subindex_half_up_rounding():
    # NH3 100 -> 50/200 * 100 = 25; Pb 0.59 -> truncates to 0.5 (50); Pb 0.60 -> 51 (CPCB How_AQI_Calculated.pdf Cp truncation)
    assert calculate_cpcb_subindex("nh3", 100.0, unit="ug/m3", averaging_period="24h") == 25
    assert calculate_cpcb_subindex("pb", 0.54, unit="ug/m3", averaging_period="24h") == 50
    assert calculate_cpcb_subindex("pb", 0.59, unit="ug/m3", averaging_period="24h") == 50
    assert calculate_cpcb_subindex("pb", 0.60, unit="ug/m3", averaging_period="24h") == 51
    # CO 0.5 mg/m3 -> (50 / 1.0) * 0.5 = 25; 1500 ug/m3 = 1.5 mg/m3 -> 73; 1.09 mg/m3 truncates to 1.0 (50)
    assert calculate_cpcb_subindex("co", 1500.0, unit="ug/m3", averaging_period="8h") == 73
    assert calculate_cpcb_subindex("co", 1.09, unit="mg/m3", averaging_period="8h") == 50
    # Final subindex Ip rounding remains ROUND_HALF_UP: NO2 = 10 -> (50/40)*10 = 12.5 -> 13 (not Python round() 12)
    assert calculate_cpcb_subindex("no2", 10.0, unit="ug/m3", averaging_period="24h") == 13


def test_cpcb_minimum_pollutant_and_particulate_gate():
    # Fewer than 3 pollutants (even with PM2.5 + PM10) -> official aqi MUST be None, never "Provisional"
    two_pm = calculate_india_cpcb_aqi({"pm25": 90.0, "pm10": 100.0})
    assert two_pm["aqi"] is None
    assert two_pm["category"] == "Unavailable"
    assert two_pm["is_reliable"] is False
    assert two_pm["dominant_pollutant"] is None
    assert two_pm["subindices"] == {"pm25": 200, "pm10": 100}
    assert two_pm["diagnostic_subindices"] == {"pm25": 200, "pm10": 100}
    assert two_pm["minimum_pollutant_requirement"]["satisfied"] is False
    assert "provisional" not in two_pm["advisory"].lower()

    # Only PM2.5 (+ 2 gases, missing PM10) -> valid
    only_pm25 = calculate_india_cpcb_aqi({"pm25": 90.0, "no2": 40.0, "so2": 40.0})
    assert only_pm25["aqi"] == 200
    assert only_pm25["dominant_pollutant"] == "PM25"
    assert only_pm25["is_reliable"] is True

    # Only PM10 (+ 2 gases, missing PM2.5) -> valid
    only_pm10 = calculate_india_cpcb_aqi({"pm10": 250.0, "co": 2.0, "o3": 50.0})
    assert only_pm10["aqi"] == 200
    assert only_pm10["dominant_pollutant"] == "PM10"
    assert only_pm10["is_reliable"] is True

    # Neither PM2.5 nor PM10 even with 4 gases -> official aqi MUST be None
    no_pm = calculate_india_cpcb_aqi({"no2": 80.0, "so2": 80.0, "co": 2.0, "o3": 100.0})
    assert no_pm["aqi"] is None
    assert no_pm["is_reliable"] is False
    assert len(no_pm["diagnostic_subindices"]) == 4

    # Missing NH3 and Pb does not prevent valid CPCB AQI when 3 other eligible pollutants exist
    with_nh3_pb = calculate_india_cpcb_aqi({"pm25": 30.0, "nh3": 1801.0, "pb": 0.5})
    assert with_nh3_pb["aqi"] == 401
    assert with_nh3_pb["dominant_pollutant"] == "NH3"


def test_cpcb_averaging_period_and_unit_eligibility_gates():
    # Reject wrong/unknown/instantaneous averaging periods
    assert calculate_cpcb_subindex("pm25", 60.0, unit="ug/m3", averaging_period="1h") is None
    assert calculate_cpcb_subindex("o3", 100.0, unit="ug/m3", averaging_period="1h") is None
    assert calculate_cpcb_subindex("co", 2.0, unit="mg/m3", averaging_period="24h") is None
    assert calculate_cpcb_subindex("pm25", 60.0, unit="ug/m3", averaging_period="unknown") is None

    # Metadata dict with unknown/instantaneous periods or missing completeness cannot qualify toward 3-pollutant minimum
    res = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            "pm25": {"value": 90.0, "unit": "ug/m3", "averaging_period": "unknown", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "pm10": {"value": 100.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "no2": {"value": 80.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "o3": {"value": 100.0, "unit": "ug/m3", "averaging_period": "instantaneous", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
        },
    )
    assert res["aqi"] is None
    assert res["minimum_pollutant_requirement"]["eligible_count"] == 2
    assert res["pollutant_provenance"]["pm25"]["classification"] == "unavailable_or_insufficient"
    assert res["pollutant_provenance"]["o3"]["classification"] == "unavailable_or_insufficient"
    assert res["pollutant_provenance"]["pm10"]["classification"] == "methodology_eligible"


@pytest.mark.parametrize("pollutant,pos_val,unit,period", [
    ("pm25", 30.0, "ug/m3", "24h"),
    ("pm10", 50.0, "ug/m3", "24h"),
    ("no2", 40.0, "ug/m3", "24h"),
    ("so2", 40.0, "ug/m3", "24h"),
    ("co", 1.0, "mg/m3", "8h"),
    ("o3", 50.0, "ug/m3", "8h"),
    ("nh3", 200.0, "ug/m3", "24h"),
    ("pb", 0.5, "ug/m3", "24h"),
])
def test_cpcb_zero_positive_negative_bool_and_non_finite_all_eight_pollutants(
    pollutant: str,
    pos_val: float,
    unit: str,
    period: str,
):
    # Legitimate 0.0 and valid positive values
    assert calculate_cpcb_subindex(pollutant, 0.0, unit=unit, averaging_period=period) == 0
    assert calculate_cpcb_subindex(pollutant, pos_val, unit=unit, averaging_period=period) == 50

    info_zero = classify_cpcb_measurement_eligibility(
        pollutant,
        {"value": 0.0, "unit": unit, "averaging_period": period, "data_origin": "measured", "valid_hours": 16, "expected_hours": 24},
    )
    assert info_zero["classification"] == "methodology_eligible"
    assert info_zero["subindex"] == 0

    for bad in [None, True, False, -0.1, -15.0, float("nan"), float("inf"), float("-inf"), "30"]:
        assert calculate_cpcb_subindex(pollutant, bad, unit=unit, averaging_period=period) is None
        assert classify_cpcb_measurement_eligibility(pollutant, bad)["classification"] == "unavailable_or_insufficient"
        info_rich = classify_cpcb_measurement_eligibility(
            pollutant,
            {"value": bad, "unit": unit, "averaging_period": period, "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
        )
        assert info_rich["classification"] == "unavailable_or_insufficient"


def test_cpcb_negative_particulate_cannot_clamp_to_zero_or_pass_pm_gate():
    # P1 FIX B regression: negative scalar PM2.5 / PM10 must NOT clamp to 0.0 or satisfy PM/3-pollutant minimum
    neg_pm25 = calculate_india_cpcb_aqi({"pm25": -15.0, "no2": 40.0, "so2": 40.0})
    assert neg_pm25["aqi"] is None
    assert neg_pm25["is_reliable"] is False
    assert neg_pm25["pollutant_provenance"]["pm25"]["reason"] == "negative_concentration"
    assert neg_pm25["pollutant_provenance"]["pm25"]["eligible_for_formula_without_origin"] is False
    assert "pm25" not in neg_pm25["subindices"]

    neg_pm10 = calculate_india_cpcb_aqi({"pm10": -5.0, "no2": 40.0, "so2": 40.0})
    assert neg_pm10["aqi"] is None
    assert neg_pm10["pollutant_provenance"]["pm10"]["reason"] == "negative_concentration"
    assert "pm10" not in neg_pm10["subindices"]


def test_cpcb_metadata_free_scalar_provenance_and_formula_only_distinction():
    # P1 FIX A: scalars without unit/period/origin are NEVER methodology_eligible & NEVER infer averaging_period
    scalar_prov = classify_cpcb_measurement_eligibility("pm25", 90.0)
    assert scalar_prov["classification"] == "unavailable_or_insufficient"
    assert scalar_prov["eligible_for_official_cpcb"] is False
    assert scalar_prov["eligible_for_formula_without_origin"] is True
    assert scalar_prov["averaging_period"] is None
    assert scalar_prov["native_unit"] is None

    # Dict missing unit, averaging_period, or data_origin is NEVER methodology_eligible
    assert classify_cpcb_measurement_eligibility("pm25", {"value": 90.0})["classification"] == "unavailable_or_insufficient"
    assert classify_cpcb_measurement_eligibility("pm25", {"value": 90.0, "unit": "ug/m3"})["classification"] == "unavailable_or_insufficient"
    assert classify_cpcb_measurement_eligibility(
        "pm25", {"value": 90.0, "unit": "ug/m3", "averaging_period": "24h", "valid_hours": 18, "expected_hours": 24}
    )["classification"] == "unavailable_or_insufficient"

    # Formula-only scalar calculation preserves API compatibility while explicitly marking non-methodology eligibility
    res_scalar = calculate_india_cpcb_aqi({"pm25": 90.0, "no2": 80.0, "nh3": 200.0})
    assert res_scalar["aqi"] == 200
    assert res_scalar["is_formula_only"] is True
    assert res_scalar["is_methodology_eligible"] is False
    assert res_scalar["is_regulatory_compliant"] is False
    assert res_scalar["calculation_basis"] == "formula_input_unverified_origin"
    assert res_scalar["minimum_pollutant_requirement"]["eligible_count"] == 0
    assert res_scalar["minimum_pollutant_requirement"]["formula_input_count"] == 3
    for p_key in ("pm25", "no2", "nh3"):
        assert res_scalar["pollutant_provenance"][p_key]["classification"] == "unavailable_or_insufficient"
        assert res_scalar["pollutant_provenance"][p_key]["averaging_period"] is None


def test_cpcb_measured_vs_model_derived_vs_provider_index_provenance():
    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    # 1. Model-derived Open-Meteo current + D.3.4.2a rolling_o3_8h -> NEVER official CPCB AQI
    model_only = {
        "pm25": NormalizedMeasurement(
            pollutant="pm25", value=75.0, unit="ug/m3", measurement_type="model_estimate",
            source="Open-Meteo CAMS", data_quality="verified", observation_timestamp=now,
            retrieval_timestamp=now, averaging_period="instantaneous", data_origin="model_derived",
        ),
        "pm10": NormalizedMeasurement(
            pollutant="pm10", value=120.0, unit="ug/m3", measurement_type="model_estimate",
            source="Open-Meteo CAMS", data_quality="verified", observation_timestamp=now,
            retrieval_timestamp=now, averaging_period="instantaneous", data_origin="model_derived",
        ),
        "no2": NormalizedMeasurement(
            pollutant="no2", value=60.0, unit="ug/m3", measurement_type="model_estimate",
            source="Open-Meteo CAMS", data_quality="verified", observation_timestamp=now,
            retrieval_timestamp=now, averaging_period="instantaneous", data_origin="model_derived",
        ),
        "so2": NormalizedMeasurement(
            pollutant="so2", value=None, unit="aqi_subindex", measurement_type="ground_observation",
            source="WAQI", data_quality="verified", observation_timestamp=now,
            retrieval_timestamp=now, original_value=140.0, original_unit="waqi_iaqi_subindex",
            averaging_period="provider_reported", data_origin="provider_index", provider_aqi_subindex=140.0,
        ),
    }
    rolling_o3 = {
        "status": "available", "value": 100.0, "unit": "ug/m3", "averaging_period": "8h",
        "valid_hours": 8, "expected_hours": 8, "completeness_ratio": 1.0,
        "completeness_policy": "model_derived_6_of_8_completeness",
        "data_origin": "model_derived", "is_regulatory_observation": False,
    }
    res_model = calculate_india_cpcb_aqi(
        {}, measurement_metadata=model_only, model_derived_aggregates={"o3_8h": rolling_o3}
    )
    assert res_model["methodology_version"] == CPCB_METHODOLOGY_VERSION
    assert res_model["aqi"] is None
    assert res_model["is_reliable"] is False
    assert res_model["is_regulatory_compliant"] is False
    assert res_model["pollutant_provenance"]["pm25"]["classification"] == "model_derived_provisional"
    assert res_model["pollutant_provenance"]["so2"]["classification"] == "provider_index"
    assert res_model["provisional_estimates"]["o3_8h"]["diagnostic_cpcb_subindex"] == 100
    assert res_model["provisional_estimates"]["o3_8h"]["is_official_cpcb_naqi"] is False

    # 2. Measured with proper CPCB periods + explicit >=16h completeness across 3+ pollutants -> methodology_eligible
    measured_ok = {
        "pm25": {"value": 90.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 16, "expected_hours": 24},
        "nh3": {"value": 400.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
        "o3": {"value": 50.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured", "valid_hours": 16, "expected_hours": 24},
    }
    res_ok = calculate_india_cpcb_aqi({}, measurement_metadata=measured_ok)
    assert res_ok["aqi"] == 200
    assert res_ok["is_methodology_eligible"] is True
    assert res_ok["calculation_basis"] == "methodology_eligible"
    assert res_ok["is_regulatory_compliant"] is False
    assert res_ok["pollutant_provenance"]["pm25"]["classification"] == "methodology_eligible"


def test_cpcb_16h_data_completeness_enforcement_and_edge_cases():
    # 1. Period label present ('24h') WITHOUT completeness metadata -> rejected (unverified), diagnostic kept
    no_comp = classify_cpcb_measurement_eligibility(
        "pm25", {"value": 90.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured"}
    )
    assert no_comp["classification"] == "unavailable_or_insufficient"
    assert no_comp["reason"] == "unverified_16h_data_completeness"
    assert no_comp["diagnostic_subindex"] == 200

    # 2. Insufficient coverage (<16h, e.g. 15h) -> rejected
    low_comp = classify_cpcb_measurement_eligibility(
        "pm25", {"value": 90.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 15, "expected_hours": 24}
    )
    assert low_comp["classification"] == "unavailable_or_insufficient"
    assert low_comp["reason"] == "insufficient_data_completeness_below_16h"

    # 3. Malformed / non-finite / bool / inconsistent completeness & sample counts -> rejected
    malformed_cases = [
        {"value": 90.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": True, "expected_hours": 24},
        {"value": 90.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": float("nan"), "expected_hours": 24},
        {"value": 90.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 20, "expected_hours": 24, "completeness_ratio": 0.2},
        {"value": 90.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24, "sample_count": 5},
        {"value": 90.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 20, "coverage_hours": 12},
        {"value": 90.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 25, "expected_hours": 24},
        # Must NOT accept fabricated 6-of-8 rule on CPCB official index
        {"value": 100.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured", "valid_hours": 6, "expected_hours": 8},
    ]
    for bad_comp in malformed_cases:
        info = classify_cpcb_measurement_eligibility("o3" if bad_comp["averaging_period"] == "8h" else "pm25", bad_comp)
        assert info["classification"] == "unavailable_or_insufficient"


@pytest.mark.asyncio
async def test_cpcb_api_and_manager_compatibility():
    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    # OpenAQ NormalizedMeasurement carries period='24h'/'8h' without 16h completeness metadata:
    # official CPCB MUST return aqi=None while preserving diagnostic_subindices.
    openaq_data = {
        "source": "OpenAQ Ground Station: Anand Vihar",
        "station_id": 5001,
        "station_name": "Anand Vihar",
        "latitude": 28.64,
        "longitude": 77.31,
        "is_ground_observation": True,
        "measurements": {
            "pm25": NormalizedMeasurement(
                pollutant="pm25", value=250.0, unit="ug/m3", measurement_type="ground_observation",
                source="OpenAQ / Anand Vihar", data_quality="verified", observation_timestamp=now,
                retrieval_timestamp=now, averaging_period="24h", data_origin="measured",
            ),
            "no2": NormalizedMeasurement(
                pollutant="no2", value=80.0, unit="ug/m3", measurement_type="ground_observation",
                source="OpenAQ / Anand Vihar", data_quality="verified", observation_timestamp=now,
                retrieval_timestamp=now, averaging_period="24h", data_origin="measured",
            ),
            "co": NormalizedMeasurement(
                pollutant="co", value=2.0, unit="mg/m3", measurement_type="ground_observation",
                source="OpenAQ / Anand Vihar", data_quality="verified", observation_timestamp=now,
                retrieval_timestamp=now, averaging_period="8h", data_origin="measured",
            ),
        },
    }

    mgr = EnvironmentalDataManager()
    with (
        patch("app.services.providers.manager.open_meteo_provider.get_current_air_quality", new=AsyncMock(return_value=None)),
        patch("app.services.providers.manager.openaq_provider.get_current_air_quality", new=AsyncMock(return_value=openaq_data)),
        patch("app.services.providers.manager.waqi_provider.get_current_air_quality", new=AsyncMock(return_value=None)),
    ):
        unified = await mgr.get_unified_air_quality(28.64, 77.31, "Delhi", "INDIA_CPCB")

    cpcb_res = unified.aqi_standard_results["INDIA_CPCB"]
    for key in ("standard", "aqi", "category", "dominant_pollutant", "color", "subindices", "advisory", "is_reliable"):
        assert key in cpcb_res
    assert cpcb_res["aqi"] is None
    assert cpcb_res["category"] == "Unavailable"
    assert cpcb_res["is_reliable"] is False
    assert cpcb_res["is_regulatory_compliant"] is False
    assert cpcb_res["diagnostic_subindices"] == {"pm25": 400, "no2": 100, "co": 100}
    assert cpcb_res["pollutant_provenance"]["pm25"]["reason"] == "unverified_16h_data_completeness"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp_valid = await client.post(
            "/api/v1/aqi/calculate?standard=INDIA_CPCB",
            json={"pm25": 90.0, "no2": 80.0, "nh3": 200.0},
        )
        assert resp_valid.status_code == 200
        assert resp_valid.json()["aqi"] == 200

        # Fewer than 3 pollutants over API returns official aqi=None
        resp_short = await client.post(
            "/api/v1/aqi/calculate?standard=INDIA_CPCB",
            json={"pm25": 90.0, "no2": 80.0},
        )
        assert resp_short.status_code == 200
        assert resp_short.json()["aqi"] is None
        assert resp_short.json()["diagnostic_subindices"] == {"pm25": 200, "no2": 100}


def test_cpcb_conditional_ozone_footnote_8h_trigger_and_1h_switch():
    """
    CPCB Table 3.1 Footnote:
    - When verified measured 8h O3 <= 208 ug/m3 (truncated Cp), official index uses 8h O3.
    - When verified measured 8h O3 > 208 ug/m3, official index MUST switch to paired measured 1h O3.
    - If paired eligible 1h O3 is missing, official O3 is unavailable (never falls back to 8h >208 or Open-Meteo).
    - Isolated 1h O3 NEVER proves the 8h > 208 trigger.
    """
    # 1. Truncated 8h Cp = 208 (from 208.9 ug/m3) stays on 8h (300) and ignores co-present paired 1h
    stay_8h = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            "pm25": {"value": 30.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "no2": {"value": 40.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "o3_8h": {
                "value": 208.9, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured",
                "valid_hours": 18, "expected_hours": 24, "station_id": "5001",
                "source": "OpenAQ / Anand Vihar (Station ID: 5001)", "observation_timestamp": "2026-05-01T12:00:00Z",
            },
            "o3_1h": {
                "value": 748.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured",
                "valid_hours": 1, "expected_hours": 1, "station_id": "5001",
                "source": "OpenAQ / Anand Vihar (Station ID: 5001)", "observation_timestamp": "2026-05-01T12:00:00Z",
            },
        },
    )
    assert stay_8h["aqi"] == 300
    assert stay_8h["subindices"]["o3"] == 300
    assert stay_8h["ozone_selection_basis"] == "o3_8h_standard"
    assert stay_8h["pollutant_provenance"]["o3_8h"]["truncated_concentration"] == 208.0
    assert stay_8h["pollutant_provenance"]["o3_1h"]["reason"] == "o3_8h_does_not_exceed_208_1h_not_applicable"

    # 2. 8h > 208 (250) + paired verified measured 1h with explicit intervals & scoped station switches to 1h
    switched = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            "pm25": {"value": 30.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "no2": {"value": 40.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "o3_8h": {
                "value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured",
                "valid_hours": 18, "expected_hours": 24, "station_id": "5001", "station_namespace": "openaq",
                "source": "OpenAQ / Anand Vihar (Station ID: 5001)",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
                "observation_timestamp": "2026-05-01T12:00:00Z",
            },
            "o3_1h": {
                "value": 478.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured",
                "valid_hours": 1, "expected_hours": 1, "station_id": "5001", "station_namespace": "openaq",
                "source": "OpenAQ / Anand Vihar (Station ID: 5001)",
                "window_start": "2026-05-01T09:00:00Z", "window_end": "2026-05-01T10:00:00Z",
                "observation_timestamp": "2026-05-01T10:00:00Z",
            },
        },
    )
    assert switched["aqi"] == 350
    assert switched["dominant_pollutant"] == "O3"
    assert switched["subindices"]["o3"] == 350
    assert switched["ozone_selection_basis"] == "o3_1h_after_8h_exceeds_208"
    assert switched["pollutant_provenance"]["o3_1h"]["classification"] == "methodology_eligible"
    assert switched["pollutant_provenance"]["o3_1h"]["station_id"] == "5001"
    assert switched["pollutant_provenance"]["o3_8h"]["station_id"] == "5001"

    # 3. 8h > 208 WITHOUT eligible 1h (e.g. only model_derived Open-Meteo O3 present) -> O3 excluded; 2 remaining pollutants -> aqi=None
    missing_1h = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            "pm25": {"value": 30.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "no2": {"value": 40.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "o3_8h": {"value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "o3": {"value": 478.0, "unit": "ug/m3", "averaging_period": "instantaneous", "data_origin": "model_derived"},
        },
    )
    assert missing_1h["aqi"] is None
    assert "o3" not in missing_1h["subindices"]
    assert missing_1h["minimum_pollutant_requirement"]["eligible_count"] == 2
    assert missing_1h["ozone_selection_basis"] == "unavailable_missing_eligible_1h_after_8h_above_208"

    # 4. Isolated 1h O3 (no verified 8h trigger) MUST NEVER qualify for official NAQI
    isolated_1h = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            "pm25": {"value": 30.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "no2": {"value": 40.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "o3_1h": {"value": 749.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured", "valid_hours": 1, "expected_hours": 1},
        },
    )
    assert isolated_1h["aqi"] is None
    assert isolated_1h["minimum_pollutant_requirement"]["eligible_count"] == 2
    assert isolated_1h["pollutant_provenance"]["o3_1h"]["reason"] == "isolated_1h_o3_cannot_prove_8h_exceeds_208_trigger"
    assert isolated_1h["diagnostic_subindices"]["o3"] == 401


def test_cpcb_truncation_cp_boundaries_across_all_tiers():
    # Official Cp truncation (ROUND_DOWN): 30.9->50, 60.9->100, 120.9->300, 250.9->400, 0.59->50, 1.09->50, 208.9->300, 748.9->400
    assert calculate_cpcb_subindex("pm25", 30.9) == 50
    assert calculate_cpcb_subindex("pm25", 60.9) == 100
    assert calculate_cpcb_subindex("pm25", 120.9) == 300
    assert calculate_cpcb_subindex("pm25", 250.9) == 400
    assert calculate_cpcb_subindex("pb", 0.59) == 50
    assert calculate_cpcb_subindex("co", 1.09) == 50
    assert calculate_cpcb_subindex("o3", 208.9, unit="ug/m3", averaging_period="8h") == 300
    assert calculate_cpcb_subindex("o3", 208.9, unit="ug/m3", averaging_period="1h") is None
    assert calculate_cpcb_subindex("o3", 209.0, unit="ug/m3", averaging_period="1h") == 301
    assert calculate_cpcb_subindex("o3", 748.9, unit="ug/m3", averaging_period="1h") == 400


def _base_cpcb_pm_no2() -> dict:
    return {
        "pm25": {"value": 30.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
        "no2": {"value": 40.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
    }


def test_cpcb_o3_pairing_same_station_and_full_curve_below_209():
    """Validly paired O3 requires scoped station IDs and explicit contained intervals, and evaluates 1h < 209 (incl. 0)."""
    # 1. Matching stable station IDs + matching namespace + different sensor IDs + 1h < 209 (180 -> 229)
    res_diff_sensors = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "o3_8h": {
                "value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured",
                "valid_hours": 18, "expected_hours": 24,
                "station_id": "5001", "station_namespace": "openaq", "sensor_id": "9001",
                "source": "OpenAQ / Anand Vihar (Station ID: 5001)",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
                "observation_timestamp": "2026-05-01T12:00:00Z", "timestamp_semantics": "period_end",
            },
            "o3_1h": {
                "value": 180.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured",
                "valid_hours": 1, "expected_hours": 1,
                "station_id": "5001", "station_namespace": "openaq", "sensor_id": "9002",
                "source": "OpenAQ / Anand Vihar (Station ID: 5001)",
                "window_start": "2026-05-01T16:30:00+05:30", "window_end": "2026-05-01T17:30:00+05:30",
                "observation_timestamp": "2026-05-01T17:30:00+05:30",  # == 12:00:00Z
            },
        },
    )
    assert res_diff_sensors["aqi"] == 229
    assert res_diff_sensors["subindices"]["o3"] == 229
    assert res_diff_sensors["dominant_pollutant"] == "O3"
    assert res_diff_sensors["is_methodology_eligible"] is True
    assert res_diff_sensors["is_regulatory_compliant"] is False
    assert res_diff_sensors["pollutant_provenance"]["o3_8h"]["sensor_id"] == "9001"
    assert res_diff_sensors["pollutant_provenance"]["o3_1h"]["sensor_id"] == "9002"

    # 2. Valid paired 1h = 0.0 (preserved zero -> 0) at earliest contained 1h interval edge [w8_start, w8_start + 1h]
    res_zero_1h = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "o3_8h": {
                "value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured",
                "valid_hours": 18, "expected_hours": 24,
                "station_id": "5001", "station_namespace": "cpcb",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_1h": {
                "value": 0.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured",
                "valid_hours": 1, "expected_hours": 1,
                "station_id": "5001", "station_namespace": "cpcb",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T05:00:00Z",
            },
        },
    )
    assert res_zero_1h["aqi"] == 50
    assert res_zero_1h["subindices"]["o3"] == 0

    # 3. Cross-midnight contained interval with UTC & IST reporting dates
    res_cross_midnight = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "o3_8h": {
                "value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured",
                "valid_hours": 18, "expected_hours": 24,
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T20:00:00Z", "window_end": "2026-05-02T04:00:00Z",
                "reporting_date": "2026-05-02", "reporting_date_timezone": "UTC",
            },
            "o3_1h": {
                "value": 478.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured",
                "valid_hours": 1, "expected_hours": 1,
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T23:00:00Z", "window_end": "2026-05-02T00:00:00Z",
                "observation_timestamp": "2026-05-02T05:30:00+05:30",  # == 00:00Z
                "reporting_date": "2026-05-02", "reporting_date_timezone": "+05:30",
            },
        },
    )
    assert res_cross_midnight["aqi"] == 350
    assert res_cross_midnight["subindices"]["o3"] == 350

    # 4. Matching explicit aliases (station_id + location_id + station_namespace + network + Source tag) agree cleanly
    res_matching_aliases = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "o3_8h": {
                "value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured",
                "valid_hours": 18, "expected_hours": 24,
                "station_id": "5001", "location_id": "5001", "station_namespace": "openaq", "network": "openaq",
                "source": "OpenAQ / Anand Vihar (Station ID: 5001)",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_1h": {
                "value": 478.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured",
                "valid_hours": 1, "expected_hours": 1,
                "site_id": "5001", "provider_namespace": "OpenAQ",
                "source": "OpenAQ / Anand Vihar (Station ID: 5001)",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
        },
    )
    assert res_matching_aliases["aqi"] == 350
    assert res_matching_aliases["subindices"]["o3"] == 350


@pytest.mark.parametrize(
    ("o3_8h_extra", "o3_1h_extra", "expected_reason_prefix"),
    [
        # 1. Missing interval bounds (on 8h and on 1h)
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "observation_timestamp": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_8h_missing_interval_bounds",
        ),
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "observation_timestamp": "2026-05-01T12:00:00Z",
            },
            "o3_1h_missing_interval_bounds",
        ),
        # 2. Caller-supplied period_end without verified interval bounds
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "observation_timestamp": "2026-05-01T12:00:00Z", "timestamp_semantics": "period_end",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "observation_timestamp": "2026-05-01T12:00:00Z", "timestamp_semantics": "period_end",
            },
            "o3_8h_missing_interval_bounds",
        ),
        # 3. Incorrect 8-hour and 1-hour interval durations
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T05:00:00Z", "window_end": "2026-05-01T12:00:00Z",  # 7h != 8h
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_8h_invalid_interval_duration",
        ),
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T10:00:00Z", "window_end": "2026-05-01T12:00:00Z",  # 2h != 1h
            },
            "o3_1h_invalid_interval_duration",
        ),
        # 4. 1-hour interval partially outside the 8-hour interval (before start & after end)
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T03:30:00Z", "window_end": "2026-05-01T04:30:00Z",
            },
            "o3_pair_1h_interval_outside_8h_interval",
        ),
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:30:00Z", "window_end": "2026-05-01T12:30:00Z",
            },
            "o3_pair_1h_interval_outside_8h_interval",
        ),
        # 5. Contradictory observation timestamps vs interval bounds
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
                "observation_timestamp": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
                "observation_timestamp": "2026-05-01T13:00:00Z",  # outside [11:00, 12:00]
            },
            "o3_1h_contradictory_observation_timestamp",
        ),
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
                "observation_timestamp": "2026-05-01T10:00:00Z", "timestamp_semantics": "period_end",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_8h_contradictory_observation_timestamp",
        ),
        # 6. Naive, malformed, and future interval timestamps
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:00:00", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_1h_naive_or_unverified_timezone_interval",
        ),
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "not-a-timestamp", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_1h_malformed_interval_bound",
        ),
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "window_end": (datetime.now(timezone.utc) + timedelta(hours=9)).isoformat(),
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                "window_end": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
            },
            "o3_8h_future_interval_bound",
        ),
        # 7. Namespace & physical station identity protections
        # 7a. Matching station IDs in different namespaces without trusted crosswalk registry
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "cpcb",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_cross_provider_without_trusted_crosswalk",
        ),
        # 7b. Missing namespace for locally scoped identifier
        (
            {
                "station_id": "5001", "source": "Anand Vihar",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "source": "Anand Vihar",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_unscoped_station_id",
        ),
        # 7c. Different station IDs with matching display names
        (
            {
                "station_id": "5001", "station_namespace": "openaq", "source": "OpenAQ / Anand Vihar",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5002", "station_namespace": "openaq", "source": "OpenAQ / Anand Vihar",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_different_station_id",
        ),
        # 7d. Matching display names without stable IDs
        (
            {
                "source": "OpenAQ / Punjabi Bagh", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "source": "OpenAQ / Punjabi Bagh", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_missing_station_id",
        ),
        # 7e. Sensor IDs without station identity
        (
            {
                "sensor_id": "9001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "sensor_id": "9001", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_missing_station_id",
        ),
        # 8. Ambiguous reporting-date timezone with valid explicit intervals
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T12:00:00Z", "window_end": "2026-05-01T20:00:00Z",
                "observation_timestamp": "2026-05-01T20:00:00Z", "reporting_date": "2026-05-01",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T19:00:00Z", "window_end": "2026-05-01T20:00:00Z",
                "observation_timestamp": "2026-05-01T20:00:00Z", "reporting_date": "2026-05-02",
            },
            "o3_1h_ambiguous_reporting_date_timezone",
        ),
        # 9. P1: Display names containing '#5'/'#1' never collide or fabricate station IDs
        (
            {
                "source": "OpenAQ / Monitoring Station #5 (Station ID: 5001)",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "source": "OpenAQ / Air Station #5 (Station ID: 9999)",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_different_station_id",
        ),
        (
            {
                "source": "OpenAQ / Central Station #1",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "source": "OpenAQ / Central Station #1",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_missing_station_id",
        ),
        # 10. P2: Matching shared_station_id cannot override same-namespace conflicting IDs or unverified crosswalks
        (
            {
                "station_id": "5001", "station_namespace": "openaq", "shared_station_id": "SITE-A",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "9999", "station_namespace": "openaq", "shared_station_id": "SITE-A",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_different_station_id",
        ),
        (
            {
                "station_id": "5001", "station_namespace": "openaq", "shared_station_id": "SITE-A",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "9999", "station_namespace": "cpcb", "shared_station_id": "SITE-A",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_cross_provider_without_trusted_crosswalk",
        ),
        # 11. P1/P2: Malformed explicit identity metadata fails closed (never falls back to source tag)
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "unknown", "station_namespace": "openaq",
                "source": "OpenAQ / Anand Vihar (Station ID: 5001)",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_malformed_station_identity",
        ),
        (
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "   ",
                "source": "OpenAQ / Anand Vihar (Station ID: 5001)",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_malformed_station_identity",
        ),
        # 12. P2.1: Conflicting explicit station IDs and conflicting namespaces must reject
        (
            {
                "station_id": "5001", "location_id": "9999", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_conflicting_station_identity_metadata",
        ),
        (
            {
                "station_id": "5001", "source": "OpenAQ / Anand Vihar (Station ID: 9999)", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_conflicting_station_identity_metadata",
        ),
        (
            {
                "station_id": "5001", "station_namespace": "openaq", "network": "cpcb",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_conflicting_station_namespace_metadata",
        ),
        # 13. P2.2: Self-declared global station identity without verified namespace fails closed
        (
            {
                "station_id": "5001", "is_global_station_id": True,
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "is_global_station_id": True,
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_unscoped_station_id",
        ),
        (
            {
                "station_id": "5001", "station_id_scope": "global",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_id_scope": "global",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_unscoped_station_id",
        ),
        # 14. P2.2: One-sided shared_station_id in same namespace must reject
        (
            {
                "station_id": "5001", "station_namespace": "openaq", "shared_station_id": "SITE-A",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            {
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_pair_different_shared_station_id",
        ),
    ],
)
def test_cpcb_o3_pairing_rejects_incompatible_station_or_window(o3_8h_extra, o3_1h_extra, expected_reason_prefix):
    """Incompatible 8h/1h O3 pairs must reject official O3 without contaminating remaining valid pollutants."""
    # Only PM2.5 + NO2 + incompatible O3 pair -> O3 excluded, so official CPCB aqi=None
    result_insufficient = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "o3_8h": {"value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24, **o3_8h_extra},
            "o3_1h": {"value": 749.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured", "valid_hours": 1, "expected_hours": 1, **o3_1h_extra},
        },
    )
    assert result_insufficient["aqi"] is None
    assert "o3" not in result_insufficient["subindices"]
    assert result_insufficient["is_regulatory_compliant"] is False
    assert result_insufficient["ozone_selection_basis"] == "unavailable_incompatible_paired_1h_after_8h_above_208"
    assert result_insufficient["pollutant_provenance"]["o3_1h"]["eligible_for_official_cpcb"] is False
    assert result_insufficient["pollutant_provenance"]["o3_1h"]["pairing_rejection_reason"] == expected_reason_prefix

    # When 3 valid non-O3 pollutants (PM2.5, NO2, SO2) are present, O3 exclusion preserves valid calculation of others
    result_with_so2 = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "so2": {"value": 80.0, "unit": "ug/m3", "averaging_period": "24h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24},
            "o3_8h": {"value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured", "valid_hours": 18, "expected_hours": 24, **o3_8h_extra},
            "o3_1h": {"value": 749.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured", "valid_hours": 1, "expected_hours": 1, **o3_1h_extra},
        },
    )
    assert result_with_so2["aqi"] == 100
    assert result_with_so2["dominant_pollutant"] == "SO2"
    assert result_with_so2["subindices"] == {"pm25": 50, "no2": 50, "so2": 100}
    assert result_with_so2["is_regulatory_compliant"] is False


def test_cpcb_o3_pairing_rejects_provider_index_1h_and_preserves_reliability_semantics():
    """Provider-index 1h O3 never pairs; formula-only mode documents is_reliable vs is_methodology_eligible."""
    res_provider_idx = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "o3_8h": {
                "value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured",
                "valid_hours": 18, "expected_hours": 24, "station_id": "5001", "observation_timestamp": "2026-05-01T12:00:00Z",
            },
            "o3_1h": {
                "value": 350.0, "unit": "aqi_subindex", "averaging_period": "1h", "data_origin": "provider_index",
                "provider_aqi_subindex": 350.0, "station_id": "5001", "observation_timestamp": "2026-05-01T12:00:00Z",
            },
        },
    )
    assert res_provider_idx["aqi"] is None
    assert "o3" not in res_provider_idx["subindices"]
    assert res_provider_idx["pollutant_provenance"]["o3_1h"]["classification"] == "provider_index"

    # Instantaneous O3 alongside 8h > 208 is also never accepted as paired 1h
    res_instant = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "o3_8h": {
                "value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured",
                "valid_hours": 18, "expected_hours": 24, "station_id": "5001", "observation_timestamp": "2026-05-01T12:00:00Z",
            },
            "o3": {
                "value": 478.0, "unit": "ug/m3", "averaging_period": "instantaneous", "data_origin": "measured",
                "valid_hours": 1, "expected_hours": 1, "station_id": "5001", "observation_timestamp": "2026-05-01T12:00:00Z",
            },
        },
    )
    assert res_instant["aqi"] is None
    assert "o3" not in res_instant["subindices"]
    assert res_instant["ozone_selection_basis"] == "unavailable_missing_eligible_1h_after_8h_above_208"

    # Provider compatibility: OpenAQ NormalizedMeasurement objects lack explicit interval bounds -> fail closed
    obs_ts = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    openaq_style = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "o3_8h": NormalizedMeasurement(
                pollutant="o3",
                value=250.0,
                unit="ug/m3",
                measurement_type="ground_observation",
                source="OpenAQ / Anand Vihar (Station ID: 5001)",
                data_quality="verified",
                observation_timestamp=obs_ts,
                retrieval_timestamp=obs_ts,
                averaging_period="8h",
                data_origin="measured",
            ),
            "o3_1h": NormalizedMeasurement(
                pollutant="o3",
                value=478.0,
                unit="ug/m3",
                measurement_type="ground_observation",
                source="OpenAQ / Anand Vihar (Station ID: 5001)",
                data_quality="verified",
                observation_timestamp=obs_ts,
                retrieval_timestamp=obs_ts,
                averaging_period="1h",
                data_origin="measured",
            ),
        },
    )
    assert openaq_style["aqi"] is None
    assert "o3" not in openaq_style["subindices"]

    # Legacy bare-scalar formula-only mode: mathematically computable (is_reliable=True), NOT methodology eligible
    formula_only = calculate_india_cpcb_aqi({"pm25": 90.0, "no2": 80.0, "nh3": 200.0})
    assert formula_only["aqi"] == 200
    assert formula_only["is_reliable"] is True
    assert formula_only["is_formula_only"] is True
    assert formula_only["is_methodology_eligible"] is False
    assert formula_only["is_regulatory_compliant"] is False
    assert formula_only["calculation_basis"] == "formula_input_unverified_origin"


def test_cpcb_p1_p2_p3_station_id_crosswalk_and_period_contradiction_regressions():
    """Verify P1 tag extraction, P2 conflicting crosswalks, and P3 contradictory key/period rejection."""
    from app.services.aqi.india_cpcb import _extract_station_id

    # P1: Display names containing '#N' never override '(Station ID: ...)' or fabricate IDs
    assert _extract_station_id(None, "OpenAQ / Monitoring Station #5 (Station ID: 5001)") == "5001"
    assert _extract_station_id(None, "OpenAQ / Air Station #5 (Station ID: 9999)") == "9999"
    assert _extract_station_id(None, "OpenAQ / Central Station #1") is None
    assert _extract_station_id(None, "OpenAQ / Site #12") is None

    # Valid pairing succeeds when both sides carry matching '(Station ID: 5001)' despite '#5' in display name
    res_hash_valid = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "o3_8h": {
                "value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured",
                "valid_hours": 18, "expected_hours": 24,
                "source": "OpenAQ / Monitoring Station #5 (Station ID: 5001)",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_1h": {
                "value": 478.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured",
                "valid_hours": 1, "expected_hours": 1,
                "source": "OpenAQ / Monitoring Station #5 (Station ID: 5001)",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
        },
    )
    assert res_hash_valid["aqi"] == 350
    assert res_hash_valid["subindices"]["o3"] == 350

    # P2.2: Caller-supplied station_crosswalk dicts cannot authorize cross-provider pairing without a server-controlled registry
    res_untrusted_cw = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "o3_8h": {
                "value": 250.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured",
                "valid_hours": 18, "expected_hours": 24,
                "station_id": "5001", "station_namespace": "openaq",
                "window_start": "2026-05-01T04:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
            "o3_1h": {
                "value": 478.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured",
                "valid_hours": 1, "expected_hours": 1,
                "station_id": "DL-AV-01", "station_namespace": "cpcb",
                "window_start": "2026-05-01T11:00:00Z", "window_end": "2026-05-01T12:00:00Z",
            },
        },
        station_crosswalk={("openaq", "5001"): "site_anand_vihar", ("cpcb", "dl-av-01"): "site_anand_vihar"},
    )
    assert res_untrusted_cw["aqi"] is None
    assert "o3" not in res_untrusted_cw["subindices"]
    assert res_untrusted_cw["pollutant_provenance"]["o3_1h"]["pairing_rejection_reason"] == "o3_pair_cross_provider_without_trusted_crosswalk"

    # P3: Contradictory key/averaging_period metadata rejected explicitly (never silently overridden)
    assert calculate_cpcb_subindex("o3_8h", 100.0, unit="ug/m3", averaging_period="1h") is None
    assert calculate_cpcb_subindex("o3_1h", 478.0, unit="ug/m3", averaging_period="8h") is None

    res_contradictory = calculate_india_cpcb_aqi(
        {},
        measurement_metadata={
            **_base_cpcb_pm_no2(),
            "o3_8h": {
                "value": 100.0, "unit": "ug/m3", "averaging_period": "1h", "data_origin": "measured",
                "valid_hours": 1, "expected_hours": 1,
            },
            "o3_1h": {
                "value": 150.0, "unit": "ug/m3", "averaging_period": "8h", "data_origin": "measured",
                "valid_hours": 18, "expected_hours": 24,
            },
        },
    )
    assert res_contradictory["aqi"] is None
    assert "o3" not in res_contradictory["subindices"]
    assert res_contradictory["pollutant_provenance"]["o3_8h"]["reason"] == "contradictory_key_and_averaging_period"
    assert res_contradictory["pollutant_provenance"]["o3_1h"]["reason"] == "contradictory_key_and_averaging_period"
