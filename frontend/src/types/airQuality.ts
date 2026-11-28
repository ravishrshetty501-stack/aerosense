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
  original_value?: number | null;
  original_unit?: string | null;
  averaging_period?: string | null;
  data_origin?: 'measured' | 'model_derived' | 'provider_index' | 'unavailable' | string | null;
  provider_aqi_subindex?: number | null;
  conversion_method?: string | null;
  conversion_assumption?: string | null;
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
  methodology_version?: string;
  aqi: number | null;
  band?: number;
  category: string;
  dominant_pollutant: string | null;
  color: string;
  subindices: Record<string, number>;
  diagnostic_subindices?: Record<string, number>;
  advisory: string;
  is_reliable: boolean;
  is_methodology_eligible?: boolean;
  is_formula_only?: boolean;
  is_regulatory_compliant?: boolean;
  calculation_basis?: string;
  ozone_selection_basis?: string | null;
  standard_note?: string;
}

export interface HourlyTrendPoint {
  time: string;
  pm25?: number | null;
  pm10?: number | null;
  no2?: number | null;
  o3?: number | null;
  us_aqi?: number | null;
  is_forecast: boolean;
  type: string;
  is_synthesized?: boolean;
}

export interface AirQualityResponse {
  location: LocationInfo;
  measurements: Record<string, NormalizedMeasurement>;
  aqi_standard_results: Record<string, AQIStandardResult>;
  dominant_pollutant: string | null;
  weather_context?: {
    elevation?: number | null;
    provider_us_aqi?: number | null;
    provider_european_aqi?: number | null;
  };
  provider_indices?: Record<string, unknown> | null;
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

export interface CityComparisonItem {
  city: string;
  country?: string | null;
  latitude: number;
  longitude: number;
  aqi: number | null;
  category?: string | null;
  color?: string | null;
  dominant_pollutant?: string | null;
  pm25?: number | null;
  pm10?: number | null;
  no2?: number | null;
  o3?: number | null;
  primary_source?: string | null;
  is_ground_observation?: boolean;
  freshness_minutes?: number | null;
}

export interface CityComparisonResponse {
  standard: AQIStandard;
  comparison: CityComparisonItem[];
}

export interface ProviderStatusInfo {
  name: string;
  role: string;
  status: string;
  details: string;
  last_successful_retrieval?: string | null;
}

export interface NetworkStatusResponse {
  status: string;
  timestamp: string;
  providers: {
    waqi?: ProviderStatusInfo;
    open_meteo?: ProviderStatusInfo;
    gemini_ai?: ProviderStatusInfo;
    openaq?: ProviderStatusInfo;
    [key: string]: ProviderStatusInfo | undefined;
  };
}

export interface ReportMeasurementItem {
  value: number | null;
  unit: string;
  type: string;
  source: string;
  timestamp?: string;
}

export interface ReportDataResponse {
  title?: string;
  city: string;
  period: string;
  generated_at: string;
  aqi_standard?: string;
  aqi_value: number | null;
  aqi_category: string;
  dominant_pollutant: string;
  primary_source: string;
  is_ground_observation: boolean;
  measurements: Record<string, ReportMeasurementItem>;
  health_advisory: string;
  forecast_summary?: string;
}
