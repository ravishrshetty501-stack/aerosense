import { describe, it, expect } from 'vitest';

describe('AeroSense AI Environmental & Atmospheric Intelligence Unit Tests', () => {
  // Test 1: WHO 2021 Reference Guideline Exposure Ratios
  it('calculates accurate WHO guideline exposure ratios', () => {
    const whoGuidelines: Record<string, number> = {
      pm25: 15.0, // 24-hr mean guideline (ug/m3)
      pm10: 45.0,
      no2: 25.0,
      so2: 40.0,
      co: 4.0,
      o3: 100.0,
    };

    const calculateExposureRatio = (pollutant: string, concentration: number) => {
      const guideline = whoGuidelines[pollutant];
      if (!guideline || guideline <= 0) return 1.0;
      return Number((concentration / guideline).toFixed(2));
    };

    // Concentration of 45 ug/m3 PM2.5 is exactly 3.0x the WHO safe threshold
    expect(calculateExposureRatio('pm25', 45.0)).toBe(3.0);

    // Concentration of 15 ug/m3 PM2.5 is exactly 1.0x (compliant)
    expect(calculateExposureRatio('pm25', 15.0)).toBe(1.0);

    // Concentration of 50 ug/m3 NO2 is 2.0x
    expect(calculateExposureRatio('no2', 50.0)).toBe(2.0);
  });

  // Test 2: Deterministic Surge / Anomaly Detection
  it('correctly flags statistical pollution surges exceeding 60% above baseline', () => {
    const detectSurgeAnomaly = (currentValue: number, baselineAverage: number) => {
      if (baselineAverage <= 0) return false;
      const surgePercent = ((currentValue - baselineAverage) / baselineAverage) * 100;
      return surgePercent >= 60;
    };

    // Baseline: 25 ug/m3; Current: 45 ug/m3 -> +80% surge -> flagged
    expect(detectSurgeAnomaly(45, 25)).toBe(true);

    // Baseline: 25 ug/m3; Current: 30 ug/m3 -> +20% fluctuation -> not flagged
    expect(detectSurgeAnomaly(30, 25)).toBe(false);

    // Baseline: 50 ug/m3; Current: 80 ug/m3 -> exactly +60% surge -> flagged
    expect(detectSurgeAnomaly(80, 50)).toBe(true);
  });

  // Test 3: Multi-Standard Category Mapping
  it('maps US EPA AQI values to official epidemiological categories', () => {
    const getUS_EPACategory = (aqi: number) => {
      if (aqi <= 50) return 'Good';
      if (aqi <= 100) return 'Moderate';
      if (aqi <= 150) return 'Unhealthy for Sensitive Groups';
      if (aqi <= 200) return 'Unhealthy';
      if (aqi <= 300) return 'Very Unhealthy';
      return 'Hazardous';
    };

    expect(getUS_EPACategory(25)).toBe('Good');
    expect(getUS_EPACategory(55)).toBe('Moderate');
    expect(getUS_EPACategory(120)).toBe('Unhealthy for Sensitive Groups');
    expect(getUS_EPACategory(180)).toBe('Unhealthy');
    expect(getUS_EPACategory(250)).toBe('Very Unhealthy');
    expect(getUS_EPACategory(350)).toBe('Hazardous');
  });

  // Test 4: Canonical City Location Deduplication
  it('deduplicates city lists by canonical name', () => {
    const rawCityList = ['Tokyo', 'London', 'Delhi', 'Tokyo', 'London'];
    const canonicalSet = Array.from(
      new Map(rawCityList.map((c) => [c.trim().toLowerCase(), c])).values()
    );

    expect(canonicalSet).toEqual(['Tokyo', 'London', 'Delhi']);
    expect(canonicalSet.length).toBe(3);
  });

  // Test 5: Theme Resolution Logic
  it('resolves system theme based on prefers-color-scheme media query', () => {
    const resolveThemeMode = (mode: 'light' | 'dark' | 'system', systemIsDark: boolean) => {
      if (mode === 'system') return systemIsDark ? 'dark' : 'light';
      return mode;
    };

    expect(resolveThemeMode('light', true)).toBe('light');
    expect(resolveThemeMode('dark', false)).toBe('dark');
    expect(resolveThemeMode('system', true)).toBe('dark');
    expect(resolveThemeMode('system', false)).toBe('light');
  });
});
