import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from app.services.providers.base import EnvironmentalProvider, NormalizedMeasurement, LocationInfo

class OpenMeteoAirQualityProvider(EnvironmentalProvider):
    """
    Open-Meteo Air Quality API client.
    Provides global hourly estimates, forecast, and historical reanalysis for PM2.5, PM10, NO2, SO2, CO, O3, US AQI, and European AQI.
    Docs: https://open-meteo.com/en/docs/air-quality-api
    """
    BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

    async def search_locations(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    self.GEOCODING_URL,
                    params={"name": query, "count": limit, "language": "en", "format": "json"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for item in data.get("results", []):
                        results.append({
                            "name": item.get("name"),
                            "city": item.get("name"),
                            "country": item.get("country"),
                            "country_code": item.get("country_code"),
                            "latitude": item.get("latitude"),
                            "longitude": item.get("longitude"),
                            "timezone": item.get("timezone", "UTC")
                        })
                    return results
            except Exception as e:
                print(f"[OpenMeteo] Geocoding lookup error: {e}")
        return []

    async def get_current_air_quality(self, lat: float, lon: float, location_name: str = "") -> Optional[Dict[str, Any]]:
        """
        Retrieves current air quality estimates and hourly series from Open-Meteo.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": [
                "pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide", 
                "sulphur_dioxide", "ozone", "us_aqi", "european_aqi"
            ],
            "hourly": [
                "pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide", 
                "sulphur_dioxide", "ozone", "us_aqi", "european_aqi"
            ],
            "past_days": 2,
            "forecast_days": 3,
            "timezone": "auto"
        }
        
        async with httpx.AsyncClient(timeout=12.0) as client:
            try:
                resp = await client.get(self.BASE_URL, params=params)
                if resp.status_code != 200:
                    print(f"[OpenMeteo] API error: status {resp.status_code}")
                    return None
                    
                data = resp.json()
                current_raw = data.get("current", {})
                current_units = data.get("current_units", {})
                obs_time_str = current_raw.get("time")
                
                try:
                    obs_time = datetime.fromisoformat(obs_time_str) if obs_time_str else datetime.now(timezone.utc)
                except Exception:
                    obs_time = datetime.now(timezone.utc)
                    
                retrieval_time = datetime.now(timezone.utc)
                
                # Normalize pollutants
                mapping = {
                    "pm25": ("pm2_5", current_units.get("pm2_5", "ug/m3")),
                    "pm10": ("pm10", current_units.get("pm10", "ug/m3")),
                    "no2":  ("nitrogen_dioxide", current_units.get("nitrogen_dioxide", "ug/m3")),
                    "so2":  ("sulphur_dioxide", current_units.get("sulphur_dioxide", "ug/m3")),
                    "co":   ("carbon_monoxide", current_units.get("carbon_monoxide", "ug/m3")),
                    "o3":   ("ozone", current_units.get("ozone", "ug/m3")),
                }
                
                measurements = {}
                for standard_key, (api_key, default_unit) in mapping.items():
                    raw_val = current_raw.get(api_key)
                    if raw_val is not None:
                        val = float(raw_val)
                        # Open-Meteo returns CO in ug/m3; standard CO is often mg/m3 in US/CPCB breakpoints
                        unit = current_units.get(api_key, default_unit)
                        if standard_key == "co" and unit == "μg/m³":
                            val = round(val / 1000.0, 2)
                            unit = "mg/m3"
                        elif unit == "μg/m³":
                            unit = "ug/m3"
                            
                        measurements[standard_key] = NormalizedMeasurement(
                            pollutant=standard_key,
                            value=val,
                            unit=unit,
                            measurement_type="model_estimate",
                            source="Open-Meteo CAMS Ensemble",
                            data_quality="verified",
                            observation_timestamp=obs_time,
                            retrieval_timestamp=retrieval_time
                        )
                        
                # Extract hourly trends & forecast
                hourly_data = data.get("hourly", {})
                times = hourly_data.get("time", [])
                hourly_pm25 = hourly_data.get("pm2_5", [])
                hourly_pm10 = hourly_data.get("pm10", [])
                hourly_no2 = hourly_data.get("nitrogen_dioxide", [])
                hourly_o3 = hourly_data.get("ozone", [])
                hourly_us_aqi = hourly_data.get("us_aqi", [])
                
                trend_records = []
                now_iso = obs_time.isoformat()
                for i, t in enumerate(times):
                    if i < len(hourly_pm25):
                        is_future = t > now_iso
                        trend_records.append({
                            "time": t,
                            "pm25": hourly_pm25[i],
                            "pm10": hourly_pm10[i] if i < len(hourly_pm10) else None,
                            "no2": hourly_no2[i] if i < len(hourly_no2) else None,
                            "o3": hourly_o3[i] if i < len(hourly_o3) else None,
                            "us_aqi": hourly_us_aqi[i] if i < len(hourly_us_aqi) else None,
                            "is_forecast": is_future,
                            "type": "forecast" if is_future else "model_estimate"
                        })
                        
                return {
                    "source": "Open-Meteo Air Quality",
                    "latitude": lat,
                    "longitude": lon,
                    "elevation": data.get("elevation", 0),
                    "timezone": data.get("timezone", "UTC"),
                    "observation_time": obs_time,
                    "retrieval_time": retrieval_time,
                    "measurements": measurements,
                    "provider_us_aqi": current_raw.get("us_aqi"),
                    "provider_european_aqi": current_raw.get("european_aqi"),
                    "hourly_series": trend_records
                }
            except Exception as e:
                print(f"[OpenMeteo] Exception querying air quality: {e}")
                return None

    async def get_hourly_trends(self, lat: float, lon: float, past_days: int = 2, forecast_days: int = 3) -> Optional[Dict[str, Any]]:
        res = await self.get_current_air_quality(lat, lon)
        if res and "hourly_series" in res:
            return {"hourly_series": res["hourly_series"]}
        return None

open_meteo_provider = OpenMeteoAirQualityProvider()
