import { describe, it, expect } from 'vitest';
import {
  formatHourlyPm25,
  getAqiScaleColor,
  resolveForecastAqi,
} from '../utils/airQualityHelpers';

describe('HourlyTrendPoint nullable pollutant handling', () => {
  it('displays em-dash instead of zero for null and undefined pollutant values', () => {
    expect(formatHourlyPm25(null)).toBe('—');
    expect(formatHourlyPm25(undefined)).toBe('—');
    expect(formatHourlyPm25(Number.NaN)).toBe('—');
  });

  it('preserves genuine 0 pollutant measurements without coercing to missing', () => {
    expect(formatHourlyPm25(0)).toBe('0 µg');
    expect(resolveForecastAqi({ us_aqi: 0, pm25: 50 })).toBe(0);
    expect(resolveForecastAqi({ us_aqi: null, pm25: 0 })).toBeNull();
    expect(getAqiScaleColor(0)).toBe('#23966B');
  });

  it('returns null instead of fabricating AQI when us_aqi is null or undefined', () => {
    expect(resolveForecastAqi({ us_aqi: null, pm25: null })).toBeNull();
    expect(resolveForecastAqi({ us_aqi: undefined, pm25: undefined })).toBeNull();
    expect(resolveForecastAqi({ us_aqi: null, pm25: undefined })).toBeNull();
    expect(resolveForecastAqi({ us_aqi: null, pm25: 20 })).toBeNull();
    expect(getAqiScaleColor(null)).toBe('#647570');
  });

  it('formats and resolves valid positive measurements without synthetic pm25 multiplier fallback', () => {
    expect(formatHourlyPm25(42.6)).toBe('43 µg');
    expect(resolveForecastAqi({ us_aqi: 118, pm25: 42.6 })).toBe(118);
    expect(resolveForecastAqi({ us_aqi: null, pm25: 20 })).toBeNull();
  });
});
