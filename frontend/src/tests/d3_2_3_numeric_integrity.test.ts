import { describe, it, expect, vi } from 'vitest';
import {
  computeComparisonAqiBounds,
  formatComparisonPollutant,
  resolveComparisonItemDisplay,
} from '../components/compare/CityComparisonView';
import {
  resolveObservationSourceStatus,
  resolveStandardAqiDisplay,
  resolveStandardBreakdownDisplay,
} from '../components/dashboard/OverviewDashboard';
import {
  formatReportConcentration,
  loadReportBriefing,
  resolveReportDisplay,
} from '../components/reports/ReportsView';
import {
  executeDeleteAlertRule,
  executeLoadAlerts,
  validateAlertRuleInput,
} from '../components/alerts/AlertsView';
import {
  AirQualityResponse,
  CityComparisonItem,
  NormalizedMeasurement,
  ReportDataResponse,
} from '../types/airQuality';
import { AlertRule } from '../types/user';

function makeMeasurement(
  value: number | null | undefined,
  measurement_type: NormalizedMeasurement['measurement_type'] = 'model_estimate'
): NormalizedMeasurement {
  return {
    pollutant: 'pm25',
    value: value as number | null,
    unit: 'µg/m³',
    measurement_type,
    source: 'Test Source',
    data_quality: 'ok',
    observation_timestamp: '2026-11-27T10:00:00Z',
    retrieval_timestamp: '2026-11-27T10:05:00Z',
  };
}

describe('Phase D.3.2.3: CityComparisonView numeric integrity & missing-data semantics', () => {
  it('computes min/max bounds across mixed finite, zero, null, NaN, and Infinity AQI values', () => {
    const items = [
      { city: 'CleanZero', latitude: 0, longitude: 0, aqi: 0 },
      { city: 'Moderate', latitude: 1, longitude: 1, aqi: 120 },
      { city: 'BadNaN', latitude: 2, longitude: 2, aqi: Number.NaN },
      { city: 'BadInf', latitude: 3, longitude: 3, aqi: Number.POSITIVE_INFINITY },
      { city: 'BadNegInf', latitude: 4, longitude: 4, aqi: Number.NEGATIVE_INFINITY },
      { city: 'MissingNull', latitude: 5, longitude: 5, aqi: null },
      { city: 'MissingUndef', latitude: 6, longitude: 6, aqi: undefined },
    ] as unknown as CityComparisonItem[];

    expect(computeComparisonAqiBounds(items)).toEqual({
      validCount: 2,
      minAqi: 0,
      maxAqi: 120,
    });
  });

  it('returns null bounds when no finite AQI readings exist', () => {
    const emptyItems = [
      { city: 'A', latitude: 0, longitude: 0, aqi: Number.NaN },
      { city: 'B', latitude: 1, longitude: 1, aqi: Number.POSITIVE_INFINITY },
      { city: 'C', latitude: 2, longitude: 2, aqi: null },
    ] as unknown as CityComparisonItem[];

    expect(computeComparisonAqiBounds(emptyItems)).toEqual({
      validCount: 0,
      minAqi: null,
      maxAqi: null,
    });
  });

  it('uses neutral color and Unavailable labels for missing/non-finite comparison items while preserving zero', () => {
    const missingItem = {
      city: 'GhostCity',
      latitude: 0,
      longitude: 0,
      aqi: Number.NaN,
      color: null,
      category: '',
      dominant_pollutant: null,
      pm25: Number.POSITIVE_INFINITY,
      pm10: Number.NEGATIVE_INFINITY,
      no2: undefined,
      o3: null,
      primary_source: '',
      is_ground_observation: false,
    } as unknown as CityComparisonItem;

    const missingDisplay = resolveComparisonItemDisplay(missingItem);
    expect(missingDisplay.hasFiniteAqi).toBe(false);
    expect(missingDisplay.aqiDisplay).toBe('—');
    expect(missingDisplay.aqiColor).toBe('#647570');
    expect(missingDisplay.category).toBe('Unavailable');
    expect(missingDisplay.dominantPollutant).toBe('Unavailable');
    expect(missingDisplay.primarySource).toBe('Unavailable');
    expect(missingDisplay.cardSourceLabel).toBe('Unavailable');
    expect(missingDisplay.tableSourceLabel).toBe('Unavailable');
    expect(formatComparisonPollutant(missingItem.pm25, 'µg/m³')).toBe('Unavailable');
    expect(formatComparisonPollutant(missingItem.pm10)).toBe('Unavailable');
    expect(formatComparisonPollutant(missingItem.no2)).toBe('Unavailable');

    const zeroGroundItem: CityComparisonItem = {
      city: 'Reykjavik',
      latitude: 64.14,
      longitude: -21.94,
      aqi: 0,
      color: '#23966B',
      category: 'Good',
      dominant_pollutant: 'PM2.5',
      pm25: 0,
      pm10: 0,
      no2: 0,
      o3: 0,
      primary_source: 'Iceland Met Office',
      is_ground_observation: true,
    };

    const zeroDisplay = resolveComparisonItemDisplay(zeroGroundItem);
    expect(zeroDisplay.hasFiniteAqi).toBe(true);
    expect(zeroDisplay.aqiDisplay).toBe(0);
    expect(zeroDisplay.aqiColor).toBe('#23966B');
    expect(zeroDisplay.cardSourceLabel).toBe('Ground Sensor');
    expect(zeroDisplay.tableSourceLabel).toBe('Ground Observation');
    expect(formatComparisonPollutant(zeroGroundItem.pm25, 'µg/m³')).toBe('0 µg/m³');
    expect(formatComparisonPollutant(-0)).toBe('0');
  });
});

describe('Phase D.3.2.3: OverviewDashboard & AQIScoreCard display integrity', () => {
  const baseResponse: AirQualityResponse = {
    location: { name: 'Tokyo', latitude: 35.68, longitude: 139.69, timezone: 'Asia/Tokyo' },
    measurements: {},
    aqi_standard_results: {},
    dominant_pollutant: null,
    hourly_history: [],
    forecast: [],
    primary_source: '',
    data_freshness_minutes: 5,
    is_ground_observation: false,
  };

  it('rejects null, undefined, NaN, and Infinity AQI without fabricating PM2.5 or healthy green color', () => {
    const nonFiniteValues = [
      null,
      undefined,
      Number.NaN,
      Number.POSITIVE_INFINITY,
      Number.NEGATIVE_INFINITY,
    ];

    for (const badAqi of nonFiniteValues) {
      const aq: AirQualityResponse = {
        ...baseResponse,
        dominant_pollutant: null,
        aqi_standard_results: {
          US_EPA: {
            standard: 'US_EPA',
            aqi: badAqi as number | null,
            category: '',
            dominant_pollutant: null,
            color: '',
            subindices: {},
            advisory: '',
            is_reliable: false,
          },
        },
      };

      const overviewDisplay = resolveStandardAqiDisplay(aq, 'US_EPA', '—');
      expect(overviewDisplay.hasFiniteAqi).toBe(false);
      expect(overviewDisplay.aqiDisplay).toBe('—');
      expect(overviewDisplay.color).toBe('#647570');
      expect(overviewDisplay.dominantPollutant).toBe('Unavailable');
      expect(overviewDisplay.category).toBe('Unavailable');

      const scoreCardDisplay = resolveStandardAqiDisplay(aq, 'US_EPA', '--');
      expect(scoreCardDisplay.aqiDisplay).toBe('--');
      expect(scoreCardDisplay.color).toBe('#647570');

      const breakdown = resolveStandardBreakdownDisplay(aq.aqi_standard_results.US_EPA, 'N/A');
      expect(breakdown).toEqual({
        hasFiniteAqi: false,
        aqiDisplay: 'N/A',
        color: '#647570',
        category: 'Unavailable',
      });
    }
  });

  it('preserves genuine 0 AQI and distinguishes ground, model, and unavailable source telemetry', () => {
    const validZeroAq: AirQualityResponse = {
      ...baseResponse,
      dominant_pollutant: 'O3',
      is_ground_observation: true,
      primary_source: 'WAQI Station #1',
      measurements: {
        pm25: makeMeasurement(0, 'ground_observation'),
        no2: makeMeasurement(Number.NaN, 'model_estimate'),
      },
      aqi_standard_results: {
        US_EPA: {
          standard: 'US_EPA',
          aqi: 0,
          category: 'Good',
          dominant_pollutant: 'O3',
          color: '#23966B',
          subindices: {},
          advisory: 'Air quality is clean.',
          is_reliable: true,
        },
      },
    };

    const resolved = resolveStandardAqiDisplay(validZeroAq, 'US_EPA');
    expect(resolved.hasFiniteAqi).toBe(true);
    expect(resolved.aqiDisplay).toBe(0);
    expect(resolved.color).toBe('#23966B');
    expect(resolved.dominantPollutant).toBe('O3');

    expect(resolveObservationSourceStatus(validZeroAq)).toEqual({
      mode: 'ground',
      primarySource: 'WAQI Station #1',
    });

    const modelOnlyAq: AirQualityResponse = {
      ...baseResponse,
      is_ground_observation: false,
      primary_source: 'Open-Meteo CAMS',
      measurements: { pm25: makeMeasurement(18.5, 'model_estimate') },
    };
    expect(resolveObservationSourceStatus(modelOnlyAq).mode).toBe('model');

    const unavailableAq: AirQualityResponse = {
      ...baseResponse,
      is_ground_observation: false,
      primary_source: '',
      measurements: {
        pm25: makeMeasurement(null, 'unavailable'),
        pm10: makeMeasurement(Number.NaN, 'model_estimate'),
        o3: makeMeasurement(Number.POSITIVE_INFINITY, 'model_estimate'),
      },
    };
    expect(resolveObservationSourceStatus(unavailableAq)).toEqual({
      mode: 'unavailable',
      primarySource: 'Unavailable',
    });
  });
});

describe('Phase D.3.2.3: ReportsView missing-data semantics & failure handling', () => {
  it('never fabricates PM2.5, Model Estimate, or numeric values when report fields are non-finite or missing', () => {
    const emptyReport = {
      city: 'Delhi',
      period: 'Daily Summary',
      generated_at: '2026-11-27T10:00:00Z',
      aqi_value: Number.NaN,
      aqi_category: '',
      dominant_pollutant: '',
      primary_source: '',
      is_ground_observation: false,
      measurements: {
        pm25: { value: Number.POSITIVE_INFINITY, unit: 'µg/m³', type: 'unavailable', source: '' },
        pm10: { value: null, unit: 'µg/m³', type: 'unavailable', source: '' },
      },
      health_advisory: '',
    } as unknown as ReportDataResponse;

    const resolved = resolveReportDisplay(emptyReport);
    expect(resolved.hasFiniteAqi).toBe(false);
    expect(resolved.aqiDisplay).toBe('—');
    expect(resolved.aqiColor).toBe('#647570');
    expect(resolved.aqiCategory).toBe('Unavailable');
    expect(resolved.dominantPollutant).toBe('Unavailable');
    expect(resolved.primarySource).toBe('Unavailable');
    expect(resolved.ingestionMode).toBe('Unavailable');
    expect(resolved.validationStatus).toBe('Data Unavailable');
    expect(formatReportConcentration(emptyReport.measurements.pm25.value)).toBe('Unavailable');
    expect(formatReportConcentration(0)).toBe('0');
  });

  it('preserves genuine 0 AQI and reports explicit error state when report fetch rejects', async () => {
    const groundZeroReport: ReportDataResponse = {
      city: 'Oslo',
      period: 'Daily Summary',
      generated_at: '2026-11-27T10:00:00Z',
      aqi_value: 0,
      aqi_category: 'Good',
      dominant_pollutant: 'PM2.5',
      primary_source: 'NILU Station',
      is_ground_observation: true,
      measurements: {
        pm25: { value: 0, unit: 'µg/m³', type: 'ground_observation', source: 'NILU' },
      },
      health_advisory: 'Satisfactory.',
    };

    const resolved = resolveReportDisplay(groundZeroReport);
    expect(resolved.hasFiniteAqi).toBe(true);
    expect(resolved.aqiDisplay).toBe(0);
    expect(resolved.ingestionMode).toBe('Ground Telemetry');
    expect(resolved.validationStatus).toBe('Quality Checked');
    expect(formatReportConcentration(groundZeroReport.measurements.pm25.value)).toBe('0');

    const okOutcome = await loadReportBriefing(
      'Oslo',
      'Daily Summary',
      'US_EPA',
      vi.fn().mockResolvedValue(groundZeroReport)
    );
    expect(okOutcome).toEqual({ data: groundZeroReport, error: null });

    const failOutcome = await loadReportBriefing(
      'Oslo',
      'Daily Summary',
      'US_EPA',
      vi.fn().mockRejectedValue(new Error('Upstream report service unavailable'))
    );
    expect(failOutcome).toEqual({
      data: null,
      error: 'Upstream report service unavailable',
    });
  });
});

describe('Phase D.3.2.3: AlertsView validation, load state, and failed-delete preservation', () => {
  it('rejects empty, whitespace, NaN, Infinity, non-numeric, and negative threshold inputs without coercing to 0', () => {
    const baseParams = { locationName: 'Tokyo', latitude: 35.68, longitude: 139.69 };

    for (const invalid of ['', '   ', 'NaN', 'Infinity', '-Infinity', 'abc', '12px', '-1', '-0.5']) {
      const result = validateAlertRuleInput({ ...baseParams, thresholdInput: invalid });
      expect(result.valid).toBe(false);
      expect(result.error).toBeTruthy();
      expect(result.threshold).toBeUndefined();
    }

    expect(
      validateAlertRuleInput({ ...baseParams, locationName: '   ', thresholdInput: '100' }).valid
    ).toBe(false);

    expect(
      validateAlertRuleInput({ locationName: 'Tokyo', thresholdInput: '100', latitude: Number.NaN, longitude: 139.69 }).valid
    ).toBe(false);

    // Explicit genuine 0 and decimal positive numbers pass
    expect(validateAlertRuleInput({ ...baseParams, thresholdInput: '0' })).toEqual({
      valid: true,
      error: null,
      locationName: 'Tokyo',
      threshold: 0,
    });
    expect(validateAlertRuleInput({ ...baseParams, thresholdInput: ' 125.5 ' })).toEqual({
      valid: true,
      error: null,
      locationName: '  Tokyo  '.trim(),
      threshold: 125.5,
    });
  });

  it('preserves existing alert rules when deletion fails and removes only the deleted rule on success', async () => {
    const sampleRules: AlertRule[] = [
      {
        id: 'rule-1',
        location_name: 'Tokyo',
        latitude: 35.68,
        longitude: 139.69,
        threshold_aqi: 100,
        pollutant: 'aqi',
        severity: 'warning',
        is_active: true,
        created_at: '2026-11-27T09:00:00Z',
      },
      {
        id: 'rule-2',
        location_name: 'Delhi',
        latitude: 28.61,
        longitude: 77.2,
        threshold_aqi: 150,
        pollutant: 'pm25',
        severity: 'critical',
        is_active: true,
        created_at: '2026-11-27T09:30:00Z',
      },
    ];

    const failedResult = await executeDeleteAlertRule(
      'rule-1',
      sampleRules,
      vi.fn().mockRejectedValue(new Error('Failed to delete alert rule'))
    );
    expect(failedResult.rules).toEqual(sampleRules);
    expect(failedResult.error).toBe('Failed to delete alert rule');

    const successResult = await executeDeleteAlertRule(
      'rule-1',
      sampleRules,
      vi.fn().mockResolvedValue(undefined)
    );
    expect(successResult.rules.map((r) => r.id)).toEqual(['rule-2']);
    expect(successResult.error).toBeNull();
  });

  it('handles unauthenticated early returns and fetch failures cleanly in executeLoadAlerts', async () => {
    const rulesSpy = vi.fn();
    const eventsSpy = vi.fn();
    const guestResult = await executeLoadAlerts(false, rulesSpy, eventsSpy);
    expect(guestResult).toEqual({ rules: [], events: [], error: null });
    expect(rulesSpy).not.toHaveBeenCalled();
    expect(eventsSpy).not.toHaveBeenCalled();

    const failResult = await executeLoadAlerts(
      true,
      vi.fn().mockRejectedValue(new Error('Network down')),
      vi.fn().mockResolvedValue([])
    );
    expect(failResult).toEqual({ rules: [], events: [], error: 'Network down' });
  });

  it('prefers per-standard dominant_pollutant and does not leak stale dominant pollutant when standard AQI is unavailable', () => {
    const multiStdAq: AirQualityResponse = {
      location: { name: 'Delhi', latitude: 28.61, longitude: 77.2, timezone: 'Asia/Kolkata' },
      measurements: {},
      dominant_pollutant: 'O3',
      hourly_history: [],
      forecast: [],
      primary_source: 'OpenAQ',
      data_freshness_minutes: 5,
      is_ground_observation: true,
      aqi_standard_results: {
        US_EPA: {
          standard: 'US_EPA',
          aqi: 120,
          category: 'Moderate',
          dominant_pollutant: 'O3',
          color: '#f59e0b',
          subindices: { o3: 120 },
          advisory: 'Moderate ozone.',
          is_reliable: true,
        },
        INDIA_CPCB: {
          standard: 'INDIA_CPCB',
          aqi: null,
          category: 'Unavailable',
          dominant_pollutant: null,
          color: '#647570',
          subindices: {},
          advisory: 'Minimum 3 pollutants required.',
          is_reliable: false,
        },
      },
    };

    const cpcbDisplay = resolveStandardAqiDisplay(multiStdAq, 'INDIA_CPCB');
    expect(cpcbDisplay.hasFiniteAqi).toBe(false);
    expect(cpcbDisplay.aqiDisplay).toBe('—');
    expect(cpcbDisplay.dominantPollutant).toBe('Unavailable');
  });

  it('uses standard-specific colors in ReportsView and labels synthesized diurnal history honestly in CSV export', async () => {
    const { buildTrajectoryCsv, buildTrajectorySeries, getStandardAqiScaleColor } = await import(
      '../utils/airQualityHelpers'
    );

    // EUROPEAN_AQI 80 (Very Poor) & 100 (Extremely Poor) use red/crimson instead of EPA yellow
    expect(getStandardAqiScaleColor(80, 'EUROPEAN_AQI')).toBe('#ef4444');
    expect(getStandardAqiScaleColor(100, 'EUROPEAN_AQI')).toBe('#7f1d1d');
    expect(getStandardAqiScaleColor(100, 'INDIA_CPCB')).toBe('#22c55e');

    const euReport: ReportDataResponse = {
      city: 'Paris',
      period: 'Daily Summary',
      generated_at: '2026-11-28T04:00:00Z',
      aqi_standard: 'EUROPEAN_AQI',
      aqi_value: 80,
      aqi_category: 'Very Poor',
      dominant_pollutant: 'PM25',
      primary_source: 'Open-Meteo CAMS',
      is_ground_observation: false,
      measurements: {},
      health_advisory: 'Very poor air quality.',
    };
    expect(resolveReportDisplay(euReport).aqiColor).toBe('#ef4444');

    const { combinedTrajectory } = buildTrajectorySeries(
      [{ time: '2026-11-28T03:00', pm25: 25, is_forecast: false, type: 'ground_anchored_reanalysis', is_synthesized: true }],
      [{ time: '2026-11-28T04:00', pm25: 28, is_forecast: true, type: 'forecast', is_synthesized: true }],
      'pm25'
    );
    const csv = buildTrajectoryCsv(combinedTrajectory, 'PM2.5', 'µg/m³');
    expect(csv).toContain('"Model-Derived Diurnal Projection"');
    expect(csv).not.toContain('"Observed"');
  });
});
