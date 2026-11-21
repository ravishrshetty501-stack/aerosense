import pytest
from app.services.aqi.engine import aqi_engine
from app.services.aqi.us_epa import calculate_us_epa_aqi, calculate_epa_subindex
from app.services.aqi.india_cpcb import calculate_india_cpcb_aqi, calculate_cpcb_subindex
from app.services.aqi.european_aqi import calculate_european_aqi, get_eaqi_band

def test_epa_subindex_pm25():
    # 12.0 ug/m3 is breakpoint for 50 (Good)
    assert calculate_epa_subindex("pm25", 12.0) == 50
    # 0 ug/m3 is 0
    assert calculate_epa_subindex("pm25", 0.0) == 0
    # 35.4 ug/m3 is breakpoint for 100 (Moderate)
    assert calculate_epa_subindex("pm25", 35.4) == 100
    # 55.4 ug/m3 is breakpoint for 150 (Sensitive)
    assert calculate_epa_subindex("pm25", 55.4) == 150
    # Extreme value (> 350.5 ug/m3) -> 401+
    assert calculate_epa_subindex("pm25", 400.0) >= 400

def test_us_epa_overall_aqi():
    measurements = {
        "pm25": 45.0,  # Unhealthy for Sensitive Groups (AQI ~124)
        "pm10": 20.0,  # Good (AQI ~19)
        "no2": 30.0,   # Good
        "o3": 40.0     # Good
    }
    result = calculate_us_epa_aqi(measurements)
    assert result["is_reliable"] is True
    assert result["dominant_pollutant"] == "PM25"
    assert result["category"] == "Unhealthy for Sensitive Groups"
    assert 101 <= result["aqi"] <= 150

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
