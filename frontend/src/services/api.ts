import { AirQualityResponse, AQIStandard, MonitoringStation } from '../types/airQuality';
import { User, AuthResponse, SavedLocation, AlertRule, AlertEvent } from '../types/user';

const API_BASE = '/api/v1';

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('aerosense_token');
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export const api = {
  // Air Quality
  async getCurrentAirQuality(params: { lat?: number; lon?: number; city?: string; standard?: AQIStandard }): Promise<AirQualityResponse> {
    const query = new URLSearchParams();
    if (params.lat !== undefined) query.set('lat', params.lat.toString());
    if (params.lon !== undefined) query.set('lon', params.lon.toString());
    if (params.city) query.set('city', params.city);
    if (params.standard) query.set('standard', params.standard);
    
    const res = await fetch(`${API_BASE}/air-quality/current?${query.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch air quality data');
    return res.json();
  },

  // Locations
  async searchLocations(q: string) {
    const res = await fetch(`${API_BASE}/locations/search?q=${encodeURIComponent(q)}`);
    if (!res.ok) return [];
    return res.json();
  },

  async getPopularCities() {
    const res = await fetch(`${API_BASE}/locations/popular`);
    if (!res.ok) return [];
    return res.json();
  },

  async getNearbyStations(lat: number, lon: number): Promise<MonitoringStation[]> {
    const res = await fetch(`${API_BASE}/locations/stations?lat=${lat}&lon=${lon}&radius=100000`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.stations || [];
  },

  // Analytics & Comparison
  async compareCities(cities: string[], standard: AQIStandard = 'US_EPA') {
    const params = new URLSearchParams();
    cities.forEach(c => params.append('cities', c));
    params.set('standard', standard);
    const res = await fetch(`${API_BASE}/analytics/compare?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to compare cities');
    return res.json();
  },

  async getTrends(lat: number, lon: number, city: string) {
    const res = await fetch(`${API_BASE}/analytics/trends?lat=${lat}&lon=${lon}&city=${encodeURIComponent(city)}`);
    if (!res.ok) throw new Error('Failed to fetch analytics');
    return res.json();
  },

  // AI Assistant
  async sendChatMessage(message: string, locationHint: string, history?: any[]) {
    const res = await fetch(`${API_BASE}/ai/chat`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        message,
        location_hint: locationHint,
        conversation_history: history,
      }),
    });
    if (!res.ok) throw new Error('Failed to communicate with AI Assistant');
    return res.json();
  },

  // Auth
  async login(email: string, password: string): Promise<AuthResponse> {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Login failed');
    }
    return res.json();
  },

  async register(data: { email: string; password: string; full_name?: string; preferred_standard?: string }): Promise<AuthResponse> {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Registration failed');
    }
    return res.json();
  },

  async getMe(): Promise<User> {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Unauthorized');
    return res.json();
  },

  // Alerts
  async getAlertRules(): Promise<AlertRule[]> {
    const res = await fetch(`${API_BASE}/alerts/rules`, { headers: getAuthHeaders() });
    if (!res.ok) return [];
    return res.json();
  },

  async createAlertRule(rule: Partial<AlertRule>): Promise<AlertRule> {
    const res = await fetch(`${API_BASE}/alerts/rules`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(rule),
    });
    if (!res.ok) throw new Error('Failed to create alert rule');
    return res.json();
  },

  async deleteAlertRule(ruleId: string): Promise<void> {
    await fetch(`${API_BASE}/alerts/rules/${ruleId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
  },

  async getAlertEvents(): Promise<AlertEvent[]> {
    const res = await fetch(`${API_BASE}/alerts/events`, { headers: getAuthHeaders() });
    if (!res.ok) return [];
    return res.json();
  },

  // Reports
  async getReportData(city: string, period: string, standard: AQIStandard) {
    const res = await fetch(`${API_BASE}/reports/data?city=${encodeURIComponent(city)}&period=${encodeURIComponent(period)}&standard=${standard}`);
    if (!res.ok) throw new Error('Failed to load report data');
    return res.json();
  },

  getReportPdfUrl(city: string, period: string, standard: AQIStandard): string {
    return `${API_BASE}/reports/export/pdf?city=${encodeURIComponent(city)}&period=${encodeURIComponent(period)}&standard=${standard}`;
  },

  // System
  async getSystemHealth() {
    const res = await fetch(`${API_BASE}/system/health`);
    if (!res.ok) throw new Error('Health check failed');
    return res.json();
  },

  async getNetworkStatus() {
    const res = await fetch(`${API_BASE}/system/network-status`);
    if (!res.ok) throw new Error('Failed to fetch network status');
    return res.json();
  }
};
