import { describe, it, expect } from 'vitest';
import { HourlyTrendPoint } from '../types/airQuality';
import {
  WHO_GUIDELINES,
  calculatePollutantExposureRatio,
  detectConcentrationSpike,
} from '../utils/airQualityHelpers';
import { resolveThemeMode } from '../context/ThemeContext';

const makeHistory = (values: Array<number | null>): HourlyTrendPoint[] =>
  values.map((val, i) => ({
    time: `2026-11-20T${String(i).padStart(2, '0')}:00:00Z`,
    pm25: val,
    pm10: null,
    no2: null,
    o3: null,
    is_forecast: false,
    type: 'model_estimate',
  }));

describe('AeroSense AI Environmental & Atmospheric Intelligence Unit Tests', () => {
  // Test 1: WHO 2021 Reference Guideline Exposure Ratios (exercising production helper)
  it('calculates accurate WHO guideline exposure ratios using production benchmarks', () => {
    expect(WHO_GUIDELINES.pm25.whoLimit).toBe(15);
    expect(WHO_GUIDELINES.no2.whoLimit).toBe(25);

    // Concentration of 45 ug/m3 PM2.5 is exactly 3.0x the WHO safe threshold
    expect(calculatePollutantExposureRatio('pm25', 45.0)).toBe(3.0);

    // Concentration of 15 ug/m3 PM2.5 is exactly 1.0x (compliant)
    expect(calculatePollutantExposureRatio('pm25', 15.0)).toBe(1.0);

    // Concentration of 50 ug/m3 NO2 is 2.0x
    expect(calculatePollutantExposureRatio('no2', 50.0)).toBe(2.0);

    // Genuine 0 reading stays 0
    expect(calculatePollutantExposureRatio('pm25', 0)).toBe(0);

    // Non-finite, negative, and missing concentrations return null safely
    expect(calculatePollutantExposureRatio('pm25', Number.NaN)).toBeNull();
    expect(calculatePollutantExposureRatio('pm25', Number.POSITIVE_INFINITY)).toBeNull();
    expect(calculatePollutantExposureRatio('pm25', Number.NEGATIVE_INFINITY)).toBeNull();
    expect(calculatePollutantExposureRatio('pm25', -5)).toBeNull();
    expect(calculatePollutantExposureRatio('pm25', null)).toBeNull();
    expect(calculatePollutantExposureRatio('pm25', undefined)).toBeNull();
  });

  // Test 2: Unified Spike Detection matching backend AlertService.detect_spike
  it('flags spikes at >= 1.6x ratio AND >= 15.0 delta, and rejects sub-threshold or missing inputs', () => {
    // Exact boundary: baseline 25 -> current 40 (ratio 1.60, delta 15.0) => flagged
    const boundaryHistory = makeHistory([25, 25, 25, 25, 25, 25]);
    const exactSpike = detectConcentrationSpike(boundaryHistory, 40, 'pm25');
    expect(exactSpike).not.toBeNull();
    expect(exactSpike?.spikeRatio).toBe(1.6);
    expect(exactSpike?.recentAverage).toBe(25);

    // Clear surge: baseline 25 -> current 45 (ratio 1.80, delta 20.0) => flagged
    const highSpike = detectConcentrationSpike(boundaryHistory, 45, 'pm25');
    expect(highSpike).not.toBeNull();
    expect(highSpike?.spikeRatio).toBe(1.8);

    // High ratio (2.0x) but below minimum delta 15.0 (baseline 10 -> current 20, delta 10) => NOT flagged
    const lowDeltaHistory = makeHistory([10, 10, 10, 10, 10, 10]);
    expect(detectConcentrationSpike(lowDeltaHistory, 20, 'pm25')).toBeNull();

    // High delta (+40.0) but below minimum ratio 1.6x (baseline 100 -> current 140, ratio 1.4x) => NOT flagged
    const lowRatioHistory = makeHistory([100, 100, 100, 100, 100, 100]);
    expect(detectConcentrationSpike(lowRatioHistory, 140, 'pm25')).toBeNull();

    // Normal fluctuation => NOT flagged
    expect(detectConcentrationSpike(boundaryHistory, 30, 'pm25')).toBeNull();

    // Missing data / insufficient history => NOT flagged
    expect(detectConcentrationSpike(makeHistory([25, 25, 25, 25, 25]), 80, 'pm25')).toBeNull();
    expect(detectConcentrationSpike(makeHistory([null, null, null, null, null, null]), 80, 'pm25')).toBeNull();
    expect(detectConcentrationSpike(boundaryHistory, null, 'pm25')).toBeNull();
    expect(detectConcentrationSpike(boundaryHistory, undefined, 'pm25')).toBeNull();

    // Zero baseline & genuine zero current reading => NOT flagged (no division by zero)
    expect(detectConcentrationSpike(makeHistory([0, 0, 0, 0, 0, 0]), 25, 'pm25')).toBeNull();
    expect(detectConcentrationSpike(boundaryHistory, 0, 'pm25')).toBeNull();

    // Six trailing missing readings with older valid history => NOT flagged
    const trailingMissing = makeHistory([25, 25, 25, 25, 25, 25, null, null, null, null, null, null]);
    expect(detectConcentrationSpike(trailingMissing, 60, 'pm25')).toBeNull();

    // Non-finite current values => NOT flagged
    expect(detectConcentrationSpike(boundaryHistory, Number.NaN, 'pm25')).toBeNull();
    expect(detectConcentrationSpike(boundaryHistory, Number.POSITIVE_INFINITY, 'pm25')).toBeNull();
    expect(detectConcentrationSpike(boundaryHistory, Number.NEGATIVE_INFINITY, 'pm25')).toBeNull();

    // Non-finite historical records excluded safely from baseline average
    const allNonFinite = makeHistory([
      Number.NaN,
      Number.POSITIVE_INFINITY,
      Number.NEGATIVE_INFINITY,
      Number.NaN,
      Number.POSITIVE_INFINITY,
      Number.NEGATIVE_INFINITY,
    ]);
    expect(detectConcentrationSpike(allNonFinite, 60, 'pm25')).toBeNull();

    const mixedNonFinite = makeHistory([
      25,
      Number.NaN,
      Number.POSITIVE_INFINITY,
      25,
      Number.NEGATIVE_INFINITY,
      25,
    ]);
    const mixedSpike = detectConcentrationSpike(mixedNonFinite, 40, 'pm25');
    expect(mixedSpike).not.toBeNull();
    expect(mixedSpike?.recentAverage).toBe(25);
    expect(mixedSpike?.spikeRatio).toBe(1.6);
  });

  // Test 3: Theme Resolution Logic (exercising production ThemeContext helper)
  it('resolves system theme based on prefers-color-scheme media query', () => {
    expect(resolveThemeMode('light', true)).toBe('light');
    expect(resolveThemeMode('dark', false)).toBe('dark');
    expect(resolveThemeMode('system', true)).toBe('dark');
    expect(resolveThemeMode('system', false)).toBe('light');
  });
});
