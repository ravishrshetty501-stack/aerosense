export type AQIStandard = 'US_EPA' | 'INDIA_CPCB' | 'EUROPEAN_AQI';

export interface NormalizedMeasurement {
  pollutant: string;
  value: number | null;
  unit: string;
  measurement_type: 'ground_observation' | 'model_estimate' | 'forecast' | 'historical' | 'stale' | 'unavailable';
  source: string;
  data_quality: string;
  observation_timestamp: string;
  retrieval_timestamp: string;
}

export interface LocationInfo {
  name: string;
  city?: string;
  country?: string;
  latitude: number;
  longitude: number;
  timezone: string;
}

export interface AQIStandardResult {
  standard: string;
  aqi: number | null;
  band?: number;
  category: string;
  dominant_pollutant: string | null;
  color: string;
  subindices: Record<string, number>;
  advisory: string;
  is_reliable: boolean;
  standard_note?: string;
}

export interface HourlyTrendPoint {
  time: string;
  pm25?: number;
  pm10?: number;
  no2?: number;
  o3?: number;
  us_aqi?: number;
  is_forecast: boolean;
  type: string;
}

export interface AirQualityResponse {
  location: LocationInfo;
  measurements: Record<string, NormalizedMeasurement>;
  aqi_standard_results: Record<string, AQIStandardResult>;
  dominant_pollutant: string | null;
  weather_context?: {
    elevation?: number;
    provider_us_aqi?: number;
    provider_european_aqi?: number;
  };
  hourly_history: HourlyTrendPoint[];
  forecast: HourlyTrendPoint[];
  primary_source: string;
  data_freshness_minutes: number;
  is_ground_observation: boolean;
}

export interface MonitoringStation {
  id: string | number;
  name: string;
  latitude: number;
  longitude: number;
  country?: string;
  provider: string;
  aqi?: number | null;
  sensors?: Array<Record<string, unknown>>;
  last_updated?: string;
  type: string;
}
