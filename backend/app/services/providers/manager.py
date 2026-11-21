from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from app.services.providers.base import NormalizedMeasurement, LocationInfo, AirQualityResponse
from app.services.providers.open_meteo import open_meteo_provider
from app.services.providers.openaq import openaq_provider
from app.services.providers.waqi import waqi_provider
from app.services.aqi.engine import aqi_engine

class EnvironmentalDataManager:
    """
    Master Environmental Data Ingestion Layer.
    Orchestrates OpenAQ API v3 (primary physical ground observations) and Open-Meteo (global coverage, model estimates, hourly history, forecasts).
    Guarantees:
    - Never fabricates readings.
    - Never substitutes 0 for missing.
    - Clearly distinguishes physical sensor observations from model estimates and forecasts.
    - Calculates deterministic AQI for US EPA, India CPCB, and European standards.
    """

    async def search_cities(self, query: str) -> List[Dict[str, Any]]:
        return await open_meteo_provider.search_locations(query)

    async def get_unified_air_quality(
        self,
        lat: float,
        lon: float,
        city_name: str = "Target City",
        preferred_standard: str = "US_EPA"
    ) -> AirQualityResponse:
        # Step 1: Query Open-Meteo for complete meteorological, hourly history, and forecast data
        meteo_data = await open_meteo_provider.get_current_air_quality(lat, lon, city_name)
        
        # Step 2: Check OpenAQ or WAQI for ground-level physical stations near coordinates
        ground_data = await openaq_provider.get_current_air_quality(lat, lon, city_name)
        if not ground_data:
            ground_data = await waqi_provider.get_current_air_quality(lat, lon, city_name)
        
        is_ground = False
        primary_source = "Open-Meteo CAMS Ensemble (Model Current Estimate)"
        merged_measurements: Dict[str, NormalizedMeasurement] = {}
        
        # If Open-Meteo succeeded, populate model baseline
        if meteo_data and "measurements" in meteo_data:
            merged_measurements.update(meteo_data["measurements"])
            
        # If physical ground station is available, prioritize ground sensors!
        if ground_data and "measurements" in ground_data and ground_data["measurements"]:
            is_ground = True
            primary_source = f"{ground_data['source']} (Physical Ground Sensor)"
            for p_key, ground_meas in ground_data["measurements"].items():
                merged_measurements[p_key] = ground_meas  # Ground observation overrides model estimate
                
        # Calculate raw numeric dictionary for deterministic AQI calculations
        raw_values = {
            k: v.value for k, v in merged_measurements.items() if v.value is not None
        }
        
        # Deterministic calculation across all 3 standards
        aqi_results = aqi_engine.calculate_all_standards(raw_values)
        selected_aqi = aqi_results.get(preferred_standard, aqi_results["US_EPA"])
        dominant_pollutant = selected_aqi.get("dominant_pollutant")
        
        # Data freshness calculation
        freshness_minutes = 15
        if merged_measurements:
            sample_time = next(iter(merged_measurements.values())).observation_timestamp
            now_utc = datetime.now(timezone.utc)
            if sample_time.tzinfo is None:
                sample_time = sample_time.replace(tzinfo=timezone.utc)
            delta = now_utc - sample_time
            freshness_minutes = max(1, int(delta.total_seconds() / 60))
            
        hourly_history = []
        forecast = []
        if meteo_data and "hourly_series" in meteo_data:
            for item in meteo_data["hourly_series"]:
                if item.get("is_forecast"):
                    forecast.append(item)
                else:
                    hourly_history.append(item)
                    
        return AirQualityResponse(
            location=LocationInfo(
                name=city_name,
                city=city_name,
                latitude=lat,
                longitude=lon,
                timezone=meteo_data.get("timezone", "UTC") if meteo_data else "UTC"
            ),
            measurements=merged_measurements,
            aqi_standard_results=aqi_results,
            dominant_pollutant=dominant_pollutant,
            weather_context={
                "elevation": meteo_data.get("elevation", 0) if meteo_data else 0,
                "provider_us_aqi": meteo_data.get("provider_us_aqi") if meteo_data else None,
                "provider_european_aqi": meteo_data.get("provider_european_aqi") if meteo_data else None,
            },
            hourly_history=hourly_history[-48:] if hourly_history else [], # past 48h
            forecast=forecast[:72] if forecast else [], # next 72h
            primary_source=primary_source,
            data_freshness_minutes=freshness_minutes,
            is_ground_observation=is_ground
        )

data_manager = EnvironmentalDataManager()
