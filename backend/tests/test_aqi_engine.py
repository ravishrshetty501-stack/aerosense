import pytest
from app.services.aqi.engine import aqi_engine
from app.services.aqi.us_epa import calculate_us_epa_aqi, calculate_epa_subindex
from app.services.aqi.india_cpcb import calculate_india_cpcb_aqi, calculate_cpcb_subindex
from app.services.aqi.european_aqi import calculate_european_aqi, get_eaqi_band

def test_epa_subindex_pm25():
    """Verify US EPA May 2024 PM2.5 breakpoints (2012 Good upper bound 12.0 -> May 2024 9.0)."""
    # May 2024 Good threshold: 0.0-9.0 ug/m3 -> 0-50
    assert calculate_epa_subindex("pm25", 0.0) == 0
    assert calculate_epa_subindex("pm25", 9.0) == 50
    # 12.0 ug/m3 shifted from 50 (Good, 2012 rule) to 56 (Moderate, May 2024 rule)
    assert calculate_epa_subindex("pm25", 12.0) == 56
    # 35.4 ug/m3 is breakpoint for 100 (Moderate)
    assert calculate_epa_subindex("pm25", 35.4) == 100
    # 55.4 ug/m3 is breakpoint for 150 (Sensitive)
    assert calculate_epa_subindex("pm25", 55.4) == 150
    # May 2024 tightened upper thresholds: 125.4->200, 225.4->300, 325.4->500
    assert calculate_epa_subindex("pm25", 125.4) == 200
    assert calculate_epa_subindex("pm25", 225.4) == 300
    assert calculate_epa_subindex("pm25", 325.4) == 500
    # Beyond the AQI (>325.4 ug/m3): Equation 1 linear extrapolation above 500 (never capped)
    assert calculate_epa_subindex("pm25", 400.0) == 649

def test_us_epa_overall_aqi():
    measurements = {
        "pm25": 45.0,  # Unhealthy for Sensitive Groups (AQI 124)
        "pm10": 20.0,  # Good (AQI 19)
        "no2": 30.0,   # Good (30 ppb -> AQI 28)
        "o3": 40.0     # Metadata-free O3 (no unit or averaging period) rejected
    }
    result = calculate_us_epa_aqi(measurements)
    assert result["is_reliable"] is True
    assert result["dominant_pollutant"] == "PM25"
    assert result["category"] == "Unhealthy for Sensitive Groups"
    assert 101 <= result["aqi"] <= 150
    assert "o3" not in result["subindices"]

def test_cpcb_subindex_pm25():
    # In CPCB: 0-30 is 0-50, 31-60 is 51-100, 61-90 is 101-200
    assert calculate_cpcb_subindex("pm25", 30.0) == 50
    assert calculate_cpcb_subindex("pm25", 60.0) == 100
    assert calculate_cpcb_subindex("pm25", 90.0) == 200

def test_cpcb_rule_missing_pm():
    # CPCB requires PM2.5 or PM10. Without PM, calculation should indicate unavailable/unreliable
    measurements = {
        "no2": 50.0,
        "so2": 25.0
    }
    result = calculate_india_cpcb_aqi(measurements)
    assert result["is_reliable"] is False
    assert result["category"] == "Unavailable"

def test_cpcb_valid_calculation():
    measurements = {
        "pm25": 75.0, # 61-90 => Moderate (101-200)
        "pm10": 110.0,
        "no2": 60.0
    }
    result = calculate_india_cpcb_aqi(measurements)
    assert result["is_reliable"] is True
    assert result["dominant_pollutant"] in ["PM25", "PM10"]
    assert result["category"] == "Moderate"

def test_european_aqi_bands():
    # PM2.5: 0-10 Good (1), 10-20 Fair (2), 20-25 Moderate (3), 25-50 Poor (4), 50-75 Very Poor (5), 75+ Extremely Poor (6)
    assert get_eaqi_band("pm25", 5.0) == 1
    assert get_eaqi_band("pm25", 15.0) == 2
    assert get_eaqi_band("pm25", 22.0) == 3
    assert get_eaqi_band("pm25", 30.0) == 4
    assert get_eaqi_band("pm25", 60.0) == 5
    assert get_eaqi_band("pm25", 90.0) == 6

def test_european_aqi_overall():
    measurements = {
        "pm25": 30.0, # Band 4 (Poor)
        "pm10": 15.0, # Band 1 (Good)
        "no2": 20.0   # Band 1 (Good)
    }
    result = calculate_european_aqi(measurements)
    assert result["is_reliable"] is True
    assert result["band"] == 4
    assert result["category"] == "Poor"
    assert result["dominant_pollutant"] == "PM25"

def test_unified_engine_dispatch():
    measurements = {"pm25": 10.0, "pm10": 20.0, "no2": 15.0}
    epa = aqi_engine.calculate(measurements, "US_EPA")
    cpcb = aqi_engine.calculate(measurements, "INDIA_CPCB")
    eu = aqi_engine.calculate(measurements, "EUROPEAN_AQI")
    
    assert epa["standard"] == "US_EPA"
    assert cpcb["standard"] == "INDIA_CPCB"
    assert eu["standard"] == "EUROPEAN_AQI"


def test_epa_and_cpcb_decimal_gaps_and_truncation_rounding_rules():
    """Verify official May 2024 EPA truncation & extrapolation and CPCB rounding eliminate breakpoint gaps without returning AQI 0."""
    # US EPA truncation (ROUND_DOWN to 0.1 for PM2.5 ug/m3 and CO ppm; integer for PM10/NO2/SO2; 0.001 ppm for O3)
    assert calculate_epa_subindex("pm25", 0) == 0
    assert calculate_epa_subindex("pm25", 9.0) == 50
    assert calculate_epa_subindex("pm25", 9.09) == 50    # truncates to 9.0 (May 2024 Good limit; was 12.0 in 2012)
    assert calculate_epa_subindex("pm25", 9.1) == 51
    assert calculate_epa_subindex("pm25", 35.4) == 100
    assert calculate_epa_subindex("pm25", 35.45) == 100  # gap value truncates to 35.4, never 0
    assert calculate_epa_subindex("pm25", 35.5) == 101
    assert calculate_epa_subindex("pm25", 325.4) == 500
    assert calculate_epa_subindex("pm25", 325.5) == 500  # 199/99.9*(325.5-225.5)+301 = 500.20 -> 500
    assert calculate_epa_subindex("pm25", 326.0) == 501  # Equation 1 extrapolation above 500 (never capped at 500)
    assert calculate_epa_subindex("pm25", 1e300) > 500
    assert calculate_epa_subindex("pm10", 54.9) == 50    # truncates to 54
    assert calculate_epa_subindex("pm10", 55.0) == 51
    # CO evaluated in EPA native ppm (4.4/4.5 ppm replace legacy mass-approximated 5.0/5.1 mg/m3)
    assert calculate_epa_subindex("co", 4.49) == 50      # truncates to 4.4 ppm
    assert calculate_epa_subindex("co", 4.5) == 51

    # India CPCB truncation (Cp ROUND_DOWN to integer for PM2.5/PM10/NO2/SO2/O3/NH3; 0.1 for CO/Pb)
    # per official CPCB How_AQI_Calculated.pdf p. 1
    assert calculate_cpcb_subindex("pm25", 0) == 0
    assert calculate_cpcb_subindex("pm25", 30.0) == 50
    assert calculate_cpcb_subindex("pm25", 30.4) == 50   # truncates to 30
    assert calculate_cpcb_subindex("pm25", 30.9) == 50   # truncates to 30, avoids gap without premature escalation
    assert calculate_cpcb_subindex("pm25", 31.0) == 51
    assert calculate_cpcb_subindex("pm25", 60.9) == 100
    assert calculate_cpcb_subindex("pm25", 61.0) == 101
    assert calculate_cpcb_subindex("pm25", 120.9) == 300 # truncates to 120, never 0
    assert calculate_cpcb_subindex("pm25", 121.0) == 301
    # Open-ended CPCB Severe (250+): documented slope interpretation in [401, 500]
    assert calculate_cpcb_subindex("pm25", 250.0) == 400
    assert calculate_cpcb_subindex("pm25", 250.9) == 400
    assert calculate_cpcb_subindex("pm25", 251.0) == 401
    assert calculate_cpcb_subindex("pm25", 350.0) == 477
    assert calculate_cpcb_subindex("pm25", 380.0) == 500
    assert calculate_cpcb_subindex("pm25", 1e300) == 500
    assert calculate_cpcb_subindex("pm10", 50.9) == 50
    assert calculate_cpcb_subindex("pm10", 51.0) == 51
    assert calculate_cpcb_subindex("co", 1.04) == 50
    assert calculate_cpcb_subindex("co", 1.09) == 50
    assert calculate_cpcb_subindex("co", 1.10) == 51

    # End-to-end CPCB calculation on decimal PM2.5 values across gaps
    cpcb_high = calculate_india_cpcb_aqi({"pm25": 120.4, "pm10": 51.0, "no2": 41.0})
    assert cpcb_high["aqi"] == 300
    assert cpcb_high["category"] == "Poor"
    assert cpcb_high["dominant_pollutant"] == "PM25"

    epa_decimal = calculate_us_epa_aqi({"pm25": 35.45})
    assert epa_decimal["aqi"] == 100
    assert epa_decimal["category"] == "Moderate"


def test_epa_and_cpcb_reject_invalid_non_finite_and_bool_inputs():
    """NaN, infinities, booleans, None, and strings must never become AQI 0 / Good / Extremely Poor."""
    invalid_values = [
        None,
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        10**400,
        -10**400,
        "42",
        "NaN",
        [],
        {},
    ]

    for bad_val in invalid_values:
        assert calculate_epa_subindex("pm25", bad_val) is None
        assert calculate_cpcb_subindex("pm25", bad_val) is None
        assert get_eaqi_band("pm25", bad_val) is None

        epa_res = calculate_us_epa_aqi({"pm25": bad_val})
        assert epa_res["aqi"] is None
        assert epa_res["category"] == "Unavailable"
        assert epa_res["is_reliable"] is False

        cpcb_res = calculate_india_cpcb_aqi({"pm25": bad_val, "pm10": bad_val, "no2": bad_val})
        assert cpcb_res["aqi"] is None
        assert cpcb_res["category"] == "Unavailable"
        assert cpcb_res["is_reliable"] is False

        eaqi_res = calculate_european_aqi({"pm25": bad_val, "pm10": bad_val})
        assert eaqi_res["aqi"] is None
        assert eaqi_res["category"] == "Unavailable"
        assert eaqi_res["is_reliable"] is False

    # Direct negative subindex rejected, while overall calculation clamps finite negative noise to 0 for EPA only
    assert calculate_epa_subindex("pm25", -0.1) is None
    assert calculate_cpcb_subindex("pm25", -0.1) is None
    assert get_eaqi_band("pm25", -0.1) is None


def test_european_aqi_provenance_and_zero_preservation():
    from app.services.aqi.engine import normalize_standard_name
    from app.services.providers.base import NormalizedMeasurement
    from datetime import datetime, timezone

    assert normalize_standard_name("cpcb") == "INDIA_CPCB"
    assert normalize_standard_name("EAQI") == "EUROPEAN_AQI"
    assert normalize_standard_name("us") == "US_EPA"

    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    meta = {
        "pm25": NormalizedMeasurement(
            pollutant="pm25", value=0.0, unit="ug/m3", measurement_type="ground_observation",
            source="Test", data_quality="verified", observation_timestamp=now, retrieval_timestamp=now, data_origin="measured",
        ),
        "o3": NormalizedMeasurement(
            pollutant="o3", value=None, unit="ppm", measurement_type="ground_observation",
            source="Test", data_quality="provisional", observation_timestamp=now, retrieval_timestamp=now,
            original_value=0.05, original_unit="ppm", data_origin="measured",
        ),
        "no2": NormalizedMeasurement(
            pollutant="no2", value=None, unit="aqi_subindex", measurement_type="ground_observation",
            source="WAQI", data_quality="verified", observation_timestamp=now, retrieval_timestamp=now,
            data_origin="provider_index", provider_aqi_subindex=150.0,
        ),
    }
    res = calculate_european_aqi({}, measurement_metadata=meta)
    assert res["aqi"] == 0
    assert res["band"] == 1
    assert res["subindices"] == {"pm25": 1}


def test_synthesize_diurnal_series_avoids_no2_ugm3_to_ppb_bug():
    from app.services.providers.base import NormalizedMeasurement
    from app.services.providers.manager import EnvironmentalDataManager
    from datetime import datetime, timezone

    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    mgr = EnvironmentalDataManager()
    # High urban NO2 = 90 ug/m3 (~48 ppb -> Good under EPA), low PM2.5 = 5 ug/m3 (~28 Good).
    # Before fix, treating 90 ug/m3 NO2 as 90 ppb yielded AQI ~89 Moderate; only mass-unit particulates should drive EPA here.
    meas = {
        "pm25": NormalizedMeasurement(
            pollutant="pm25", value=5.0, unit="ug/m3", measurement_type="model_estimate",
            source="CAMS", data_quality="verified", observation_timestamp=now, retrieval_timestamp=now, data_origin="model_derived",
        ),
        "no2": NormalizedMeasurement(
            pollutant="no2", value=90.0, unit="ug/m3", measurement_type="model_estimate",
            source="CAMS", data_quality="verified", observation_timestamp=now, retrieval_timestamp=now, data_origin="model_derived",
        ),
    }
    hist, fc = mgr._synthesize_diurnal_series(meas, ref_time=now)
    assert len(hist) == 48 and len(fc) == 72
    assert hist[-1]["us_aqi"] <= 50
