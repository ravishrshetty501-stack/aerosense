import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '../services/api';
import { openReportPdf } from '../components/reports/ReportsView';

describe('AeroSense AI Frontend API Service Client Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // In-memory localStorage mock
    const storage: Record<string, string> = {};
    global.localStorage = {
      getItem: (key: string) => storage[key] || null,
      setItem: (key: string, value: string) => { storage[key] = value; },
      removeItem: (key: string) => { delete storage[key]; },
      clear: () => { Object.keys(storage).forEach((k) => delete storage[k]); },
      length: 0,
      key: (i: number) => Object.keys(storage)[i] || null,
    };
  });

  it('constructs correct PDF export URL with query parameters', () => {
    const url = api.getReportPdfUrl('New York', 'Daily Summary', 'US_EPA');
    expect(url).toBe('/api/v1/reports/export/pdf?city=New%20York&period=Daily%20Summary&standard=US_EPA');
  });

  it('serializes air quality parameters correctly in getCurrentAirQuality', async () => {
    let capturedUrl = '';
    global.fetch = vi.fn().mockImplementation((url: string) => {
      capturedUrl = url;
      return Promise.resolve({
        ok: true,
        json: async () => ({
          location: { name: 'Tokyo', city: 'Tokyo', latitude: 35.68, longitude: 139.69, timezone: 'Asia/Tokyo' },
          measurements: {},
          aqi_standard_results: {}
        }),
      } as Response);
    });

    const result = await api.getCurrentAirQuality({
      lat: 35.68,
      lon: 139.69,
      city: 'Tokyo',
      standard: 'US_EPA',
    });

    expect(capturedUrl).toContain('/api/v1/air-quality/current?');
    expect(capturedUrl).toContain('lat=35.68');
    expect(capturedUrl).toContain('lon=139.69');
    expect(capturedUrl).toContain('city=Tokyo');
    expect(capturedUrl).toContain('standard=US_EPA');
    expect(result.location.name).toBe('Tokyo');
  });

  it('properly encodes query string in searchLocations', async () => {
    let capturedUrl = '';
    global.fetch = vi.fn().mockImplementation((url: string) => {
      capturedUrl = url;
      return Promise.resolve({
        ok: true,
        json: async () => [{ name: 'San Francisco', latitude: 37.77, longitude: -122.41 }],
      } as Response);
    });

    const results = await api.searchLocations('San Francisco');
    expect(capturedUrl).toBe('/api/v1/locations/search?q=San%20Francisco');
    expect(results.length).toBe(1);
    expect(results[0].name).toBe('San Francisco');
  });

  it('serializes multiple city names in compareCities', async () => {
    let capturedUrl = '';
    global.fetch = vi.fn().mockImplementation((url: string) => {
      capturedUrl = url;
      return Promise.resolve({
        ok: true,
        json: async () => ({ standard: 'US_EPA', comparison: [] }),
      } as Response);
    });

    await api.compareCities(['London', 'Tokyo', 'Paris'], 'US_EPA');
    expect(capturedUrl).toContain('/api/v1/analytics/compare?');
    expect(capturedUrl).toContain('cities=London');
    expect(capturedUrl).toContain('cities=Tokyo');
    expect(capturedUrl).toContain('cities=Paris');
    expect(capturedUrl).toContain('standard=US_EPA');
  });

  it('injects Bearer token in authenticated requests when present', async () => {
    localStorage.setItem('aerosense_token', 'test-jwt-token-xyz');
    let capturedHeaders: Record<string, string> = {};

    global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      capturedHeaders = (init?.headers || {}) as Record<string, string>;
      return Promise.resolve({
        ok: true,
        json: async () => ({ email: 'test@aerosense.ai', id: 'uid-1' }),
      } as Response);
    });

    const user = await api.getMe();
    expect(capturedHeaders['Authorization']).toBe('Bearer test-jwt-token-xyz');
    expect(user.email).toBe('test@aerosense.ai');
  });

  it('throws descriptive error on login failure', async () => {
    global.fetch = vi.fn().mockImplementation(() => {
      return Promise.resolve({
        ok: false,
        json: async () => ({ detail: 'Incorrect email or password' }),
      } as Response);
    });

    await expect(api.login('user@aerosense.ai', 'wrongpass')).rejects.toThrow('Incorrect email or password');
  });

  it('sends correct JSON payload during user registration', async () => {
    let capturedBody = '';
    global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      capturedBody = init?.body as string;
      return Promise.resolve({
        ok: true,
        json: async () => ({ access_token: 'new-token', token_type: 'bearer' }),
      } as Response);
    });

    const regData = {
      email: 'newuser@aerosense.ai',
      password: 'SecurePass123!',
      full_name: 'Test Analyst',
      preferred_standard: 'INDIA_CPCB',
    };

    const res = await api.register(regData);
    expect(res.access_token).toBe('new-token');
    const parsedBody = JSON.parse(capturedBody);
    expect(parsedBody.email).toBe('newuser@aerosense.ai');
    expect(parsedBody.preferred_standard).toBe('INDIA_CPCB');
  });

  it('handles missing city in getReportPdfUrl and enforces noopener,noreferrer when opening PDFs', () => {
    expect(api.getReportPdfUrl('', 'Daily Summary', 'US_EPA')).toBe('');
    expect(api.getReportPdfUrl('   ', 'Daily Summary', 'US_EPA')).toBe('');

    const validUrl = api.getReportPdfUrl('Tokyo', 'Daily Summary', 'US_EPA');
    expect(validUrl).toBe('/api/v1/reports/export/pdf?city=Tokyo&period=Daily%20Summary&standard=US_EPA');

    const openSpy = vi.fn().mockReturnValue(null);
    const okResult = openReportPdf(validUrl, openSpy);
    expect(openSpy).toHaveBeenCalledWith(validUrl, '_blank', 'noopener,noreferrer');
    expect(okResult).toEqual({ opened: true, error: null });

    // Missing or non-http/relative URLs fail cleanly without invoking window.open
    const neverCalled = vi.fn();
    const emptyOutcome = openReportPdf('', neverCalled);
    expect(emptyOutcome.opened).toBe(false);
    expect(emptyOutcome.error).toBeTruthy();
    expect(neverCalled).not.toHaveBeenCalled();

    const unsafeSchemeOutcome = openReportPdf('javascript:alert(1)', neverCalled);
    expect(unsafeSchemeOutcome.opened).toBe(false);
    expect(unsafeSchemeOutcome.error).toBeTruthy();
    expect(neverCalled).not.toHaveBeenCalled();

    // Thrown window.open error is caught and reported cleanly
    const throwingOpen = vi.fn().mockImplementation(() => {
      throw new Error('Blocked');
    });
    const failedOutcome = openReportPdf(validUrl, throwingOpen);
    expect(failedOutcome.opened).toBe(false);
    expect(failedOutcome.error).toBeTruthy();
  });

  it('throws an error when deleteAlertRule receives a non-OK HTTP response', async () => {
    global.fetch = vi.fn().mockImplementation(() => {
      return Promise.resolve({
        ok: false,
        status: 500,
      } as Response);
    });

    await expect(api.deleteAlertRule('rule-123')).rejects.toThrow('Failed to delete alert rule');
  });

  it('throws descriptive errors on non-OK alert fetches, non-JSON login errors, and forwards signal in compareCities', async () => {
    global.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Unauthorized' }),
      } as Response)
    );
    await expect(api.getAlertRules()).rejects.toThrow('Unauthorized');
    await expect(api.getAlertEvents()).rejects.toThrow('Unauthorized');

    global.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: false,
        status: 502,
        json: async () => {
          throw new SyntaxError('Unexpected token <');
        },
      } as unknown as Response)
    );
    await expect(api.login('user@aerosense.ai', 'pass')).rejects.toThrow('Login failed (HTTP 502)');

    let capturedInit: RequestInit | undefined;
    global.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      capturedInit = init;
      return Promise.resolve({
        ok: true,
        json: async () => ({ standard: 'US_EPA', comparison: [] }),
      } as Response);
    });
    const controller = new AbortController();
    await api.compareCities(['Tokyo', 'London'], 'US_EPA', { signal: controller.signal });
    expect(capturedInit?.signal).toBe(controller.signal);
  });
});
