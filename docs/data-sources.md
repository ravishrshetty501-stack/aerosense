# Environmental Data Sources & Integrity
**AeroSense AI — Data Ingestion Architecture**

---

## 1. Primary Provider: OpenAQ API v3

- **Endpoint**: `https://api.openaq.org/v3`
- **Role**: Primary provider for physical ground-level environmental monitoring stations.
- **Data Retrieved**:
  - Global monitoring locations (`/v3/locations`)
  - Sensor definitions (`/v3/sensors`)
  - Latest observed ground-level measurements (`/v3/locations/{id}/latest`)
  - Geographic latitude, longitude, and elevation
  - Sensor timestamps and raw concentration units
- **Authentication**: `OPENAQ_API_KEY` passed via `X-API-Key` HTTP header.
- **Classification**: Tagged as `measurement_type = "ground_observation"` with source attribution to the physical station name and provider.

---

## 2. Secondary Provider: Open-Meteo Air Quality API

- **Endpoint**: `https://air-quality-api.open-meteo.com/v1/air-quality`
- **Role**: Secondary provider for continuous global spatial coverage, hourly historical reanalysis (past 48-72 hours), and 5-day predictive forecasts.
- **Model Foundation**: Copernicus Atmosphere Monitoring Service (CAMS) ensemble and NOAA GFS-Aerosol global chemistry models.
- **Pollutants Monitored**:
  - `pm2_5`: Fine particulate matter (µg/m³)
  - `pm10`: Coarse particulate matter (µg/m³)
  - `nitrogen_dioxide`: NO₂ (µg/m³)
  - `sulphur_dioxide`: SO₂ (µg/m³)
  - `carbon_monoxide`: CO (converted from µg/m³ to standard mg/m³)
  - `ozone`: O₃ (µg/m³)
  - `us_aqi` & `european_aqi` estimates
- **Classification**: Tagged as `measurement_type = "model_estimate"` or `measurement_type = "forecast"`.

---

## 3. Data Integrity & Scientific Ethics Rules

1. **Physical Sensor vs Model Distinction**:
   Model estimates are NEVER represented as physical sensor readings. If an OpenAQ station is within range, physical observations override model estimates, and the UI highlights an active ground sensor badge.
2. **No Value Fabrication**:
   If a pollutant is not monitored at a station or coordinate, the system records `null` (or `None`). It **never** substitutes zero for missing values, as zero indicates pure air rather than absence of measurement.
3. **Observation vs Retrieval Timestamps**:
   Every measurement records both `observation_timestamp` (when the sample was observed) and `retrieval_timestamp` (when AeroSense AI ingested it).
4. **Data Freshness Indicator**:
   The user interface features a real-time data freshness counter computing minutes elapsed since the primary sample was taken.
