from datetime import datetime, timezone
from app.services.providers.base import NormalizedMeasurement
from app.services.providers.manager import EnvironmentalDataManager


def test_synthesize_diurnal_series_preserves_missing_pollutants():
    """Missing pollutants must remain None rather than being fabricated from defaults."""
    mgr = EnvironmentalDataManager()
    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    measurements = {
        "pm25": NormalizedMeasurement(
            pollutant="pm25",
            value=80.0,
            unit="ug/m3",
            measurement_type="ground_observation",
            source="WAQI Ground Station",
            data_quality="verified",
            observation_timestamp=now,
            retrieval_timestamp=now,
        )
    }

    history, forecast = mgr._synthesize_diurnal_series(measurements, ref_time=now)

    assert len(history) == 48
    assert len(forecast) == 72

    for pt in history + forecast:
        assert pt["pm25"] is not None and pt["pm25"] > 0
        assert pt["pm10"] is None
        assert pt["no2"] is None
        assert pt["o3"] is None
        assert pt["us_aqi"] is not None


def test_synthesize_diurnal_series_returns_empty_when_no_tracked_pollutants():
    """If no tracked trajectory pollutants are measured, return empty lists rather than fabricating."""
    mgr = EnvironmentalDataManager()
    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    measurements = {
        "co": NormalizedMeasurement(
            pollutant="co",
            value=1.2,
            unit="mg/m3",
            measurement_type="ground_observation",
            source="WAQI Ground Station",
            data_quality="verified",
            observation_timestamp=now,
            retrieval_timestamp=now,
        )
    }

    history, forecast = mgr._synthesize_diurnal_series(measurements, ref_time=now)

    assert history == []
    assert forecast == []
