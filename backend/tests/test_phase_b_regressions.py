from datetime import datetime, timezone
from app.services.providers.base import NormalizedMeasurement
from app.services.providers.manager import EnvironmentalDataManager


def test_synthesize_diurnal_series_consolidated_history_and_forecast_continuity():
    """Verify consolidated diurnal point builder produces contiguous 48h history + 72h forecast."""
    mgr = EnvironmentalDataManager()
    ref = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    measurements = {
        "pm25": NormalizedMeasurement(
            pollutant="pm25",
            value=50.0,
            unit="ug/m3",
            measurement_type="ground_observation",
            source="WAQI",
            data_quality="verified",
            observation_timestamp=ref,
            retrieval_timestamp=ref,
        ),
        "o3": NormalizedMeasurement(
            pollutant="o3",
            value=40.0,
            unit="ug/m3",
            measurement_type="ground_observation",
            source="WAQI",
            data_quality="verified",
            observation_timestamp=ref,
            retrieval_timestamp=ref,
        ),
    }

    history, forecast = mgr._synthesize_diurnal_series(measurements, ref_time=ref)

    assert len(history) == 48
    assert len(forecast) == 72

    assert history[0]["time"] == "2026-11-25T12:00"
    assert history[-1]["time"] == "2026-11-27T11:00"
    assert all(pt["is_forecast"] is False and pt["type"] == "ground_anchored_reanalysis" for pt in history)

    assert forecast[0]["time"] == "2026-11-27T13:00"
    assert forecast[-1]["time"] == "2026-11-30T12:00"
    assert all(pt["is_forecast"] is True and pt["type"] == "forecast" for pt in forecast)

    # Unmeasured pollutants stay None in both series
    assert all(pt["pm10"] is None and pt["no2"] is None for pt in history + forecast)


def test_synthesize_diurnal_series_preserves_genuine_zero():
    """Verify genuine 0.0 measurements remain 0.0 (not treated as missing/None)."""
    mgr = EnvironmentalDataManager()
    ref = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    measurements = {
        "pm25": NormalizedMeasurement(
            pollutant="pm25",
            value=0.0,
            unit="ug/m3",
            measurement_type="ground_observation",
            source="WAQI",
            data_quality="verified",
            observation_timestamp=ref,
            retrieval_timestamp=ref,
        )
    }

    history, forecast = mgr._synthesize_diurnal_series(measurements, ref_time=ref)

    assert len(history) == 48
    assert len(forecast) == 72
    assert all(pt["pm25"] == 0.0 for pt in history + forecast)
    assert all(pt["pm10"] is None and pt["no2"] is None and pt["o3"] is None for pt in history + forecast)
    assert all(pt["us_aqi"] == 0 for pt in history + forecast)
