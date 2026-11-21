export interface User {
  id: string;
  email: string;
  full_name?: string;
  preferred_standard: string;
  theme: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface SavedLocation {
  id: string;
  name: string;
  country?: string;
  latitude: number;
  longitude: number;
  is_favorite: boolean;
}

export interface AlertRule {
  id: string;
  location_name: string;
  latitude: number;
  longitude: number;
  threshold_aqi: number;
  pollutant: string;
  severity: string;
  is_active: boolean;
  created_at: string;
}

export interface AlertEvent {
  id: string;
  rule_id: string;
  location_name: string;
  trigger_value: number;
  threshold_value: number;
  pollutant: string;
  severity: string;
  message: string;
  acknowledged: boolean;
  triggered_at: string;
}
