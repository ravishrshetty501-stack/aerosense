from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

class NormalizedMeasurement(BaseModel):
    pollutant: str                    # pm25, pm10, no2, so2, co, o3
    value: Optional[float] = None     # normalized concentration (ug/m3, mg/m3 for CO), None if unavailable/unconverted
    unit: str                         # normalized unit, original unit when unconverted, or aqi_subindex/unavailable
    measurement_type: str             # ground_observation, model_estimate, forecast, historical, stale, unavailable
    source: str                       # e.g. "OpenAQ / Station Alpha", "Open-Meteo CAMS Ensemble"
    data_quality: str                 # verified, provisional, estimated, unavailable
    observation_timestamp: datetime
    retrieval_timestamp: datetime
    # Additive D.3.4.1 provenance metadata (all optional for consumer compatibility)
    original_value: Optional[float] = None
    original_unit: Optional[str] = None
    averaging_period: Optional[str] = None
    data_origin: Optional[str] = None            # measured, model_derived, provider_index, unavailable
    provider_aqi_subindex: Optional[float] = None
    conversion_method: Optional[str] = None
    conversion_assumption: Optional[str] = None

class LocationInfo(BaseModel):
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: float
    longitude: float
    timezone: str = "UTC"

class AirQualityResponse(BaseModel):
    location: LocationInfo
    measurements: Dict[str, NormalizedMeasurement]
    aqi_standard_results: Dict[str, Any]
    dominant_pollutant: Optional[str] = None
    weather_context: Optional[Dict[str, Any]] = None # temp, humidity, wind_speed
    provider_indices: Optional[Dict[str, Any]] = None # separate provider-reported AQI indices (WAQI / Open-Meteo)
    model_derived_aggregates: Optional[Dict[str, Any]] = None # model-derived rolling summaries (e.g. Open-Meteo 8h O3)
    hourly_history: Optional[List[Dict[str, Any]]] = None # past 24-72h real points
    forecast: Optional[List[Dict[str, Any]]] = None # upcoming hours
    primary_source: str
    data_freshness_minutes: int
    is_ground_observation: bool

class EnvironmentalProvider(ABC):
    @abstractmethod
    async def get_current_air_quality(self, lat: float, lon: float, location_name: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def get_hourly_trends(self, lat: float, lon: float, past_days: int = 2, forecast_days: int = 3) -> Optional[Dict[str, Any]]:
        pass
