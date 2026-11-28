import { describe, it, expect, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

// Mock maplibre-gl so module import succeeds cleanly in Node environment
vi.mock('maplibre-gl', () => ({
  default: {
    Map: vi.fn(),
    Marker: vi.fn(),
    Popup: vi.fn(),
    AttributionControl: vi.fn(),
    ScaleControl: vi.fn(),
  },
}));

import {
  buildCityPopupElement,
  buildStationPopupElement,
  filterStationsByAqiTier,
  selectTemporalTimelinePoints,
  buildMapTelemetrySummary,
} from '../components/map/GlobalPollutionMap';
import { AirQualityResponse, HourlyTrendPoint, MonitoringStation, NormalizedMeasurement } from '../types/airQuality';

interface MockElement {
  tagName: string;
  style: Record<string, string>;
  textContent: string | null;
  children: MockElement[];
  appendChild: (child: MockElement) => MockElement;
}

function createMockDocument(): Document {
  const createEl = (tag: string): MockElement => {
    const el: MockElement = {
      tagName: tag.toUpperCase(),
      style: {},
      textContent: null,
      children: [],
      appendChild(child: MockElement) {
        this.children.push(child);
        return child;
      },
    };
    return el;
  };
  return { createElement: createEl } as unknown as Document;
}

describe('GlobalPollutionMap safe DOM popup builders', () => {
  it('renders city focus popup via textContent without HTML interpolation', () => {
    const mockDoc = createMockDocument();
    const xssPayload = '<img src=x onerror=alert(1)>Delhi';
    const root = buildCityPopupElement(xssPayload, 28.6139, 77.2090, mockDoc) as unknown as MockElement;

    expect(root.children.length).toBe(3);
    expect(root.children[0].textContent).toBe(xssPayload);
    expect(root.children[1].textContent).toBe('Geographical Focus Location');
    expect(root.children[2].textContent).toBe('28.6139°N, 77.2090°E');
    // Ensure innerHTML was never set
    expect((root as unknown as Record<string, unknown>).innerHTML).toBeUndefined();
    expect((root.children[0] as unknown as Record<string, unknown>).innerHTML).toBeUndefined();
  });

  it('renders monitoring station popup via textContent with N/A fallback for missing AQI', () => {
    const mockDoc = createMockDocument();
    const stationName = '<script>alert("xss")</script>Mandir Marg';
    const providerName = '<b>WAQI</b> <svg onload=alert(1)>';

    const root = buildStationPopupElement(
      { name: stationName, aqi: null, provider: providerName },
      '#159DB0',
      mockDoc
    ) as unknown as MockElement;

    expect(root.children.length).toBe(3);
    const header = root.children[0];
    expect(header.children[0].textContent).toBe('AQI N/A');
    expect(header.children[0].style.color).toBe('#159DB0');
    expect(header.children[1].textContent).toBe('Ground Station');
    expect(root.children[1].textContent).toBe(stationName);
    expect(root.children[2].textContent).toBe(`Provider: ${providerName}`);
  });

  it('uses theme-adaptive CSS variables for popup text readability and preserves genuine 0 AQI', () => {
    const mockDoc = createMockDocument();
    const cityRoot = buildCityPopupElement('Tokyo', 35.6895, 139.6917, mockDoc) as unknown as MockElement;
    expect(cityRoot.children[0].style.color).toContain('var(--accent-primary');
    expect(cityRoot.children[1].style.color).toContain('var(--text-secondary');
    expect(cityRoot.children[2].style.color).toContain('var(--text-primary');
    expect(cityRoot.children[2].style.color).not.toBe('#172B28');

    const zeroStation = buildStationPopupElement(
      { name: 'Clean Station', aqi: 0, provider: 'WAQI' },
      '#23966B',
      mockDoc
    ) as unknown as MockElement;
    expect(zeroStation.children[0].children[0].textContent).toBe('AQI 0');
    expect(zeroStation.children[0].children[1].style.color).toContain('var(--text-secondary');
    expect(zeroStation.children[1].style.color).toContain('var(--text-primary');
    expect(zeroStation.children[1].style.color).not.toBe('#172B28');
    expect(zeroStation.children[2].style.color).toContain('var(--text-secondary');

    const nanStation = buildStationPopupElement(
      { name: 'Invalid Station', aqi: Number.NaN, provider: 'WAQI' },
      '#159DB0',
      mockDoc
    ) as unknown as MockElement;
    expect(nanStation.children[0].children[0].textContent).toBe('AQI N/A');
  });
});

describe('GlobalPollutionMap filtering, temporal step, telemetry summary, and CSS integrity', () => {
  const sampleStations: MonitoringStation[] = [
    { id: 1, name: 'Zero Station', latitude: 0, longitude: 0, provider: 'WAQI', aqi: 0, type: 'ground_station' },
    { id: 2, name: 'Good Station', latitude: 0, longitude: 0, provider: 'WAQI', aqi: 50, type: 'ground_station' },
    { id: 3, name: 'Mod Station', latitude: 0, longitude: 0, provider: 'WAQI', aqi: 51, type: 'ground_station' },
    { id: 4, name: 'Poor Station', latitude: 0, longitude: 0, provider: 'WAQI', aqi: 120, type: 'ground_station' },
    { id: 5, name: 'Severe Station', latitude: 0, longitude: 0, provider: 'WAQI', aqi: 210, type: 'ground_station' },
    { id: 6, name: 'Null Station', latitude: 0, longitude: 0, provider: 'WAQI', aqi: null, type: 'ground_station' },
    { id: 7, name: 'Undefined Station', latitude: 0, longitude: 0, provider: 'WAQI', type: 'ground_station' },
    { id: 8, name: 'NaN Station', latitude: 0, longitude: 0, provider: 'WAQI', aqi: Number.NaN, type: 'ground_station' },
  ];

  it('excludes null/missing/non-finite station AQIs from numeric tiers and preserves genuine 0', () => {
    expect(filterStationsByAqiTier(sampleStations, 'all')).toHaveLength(8);
    expect(filterStationsByAqiTier(sampleStations, 'good').map((s) => s.name)).toEqual([
      'Zero Station',
      'Good Station',
    ]);
    expect(filterStationsByAqiTier(sampleStations, 'moderate').map((s) => s.name)).toEqual(['Mod Station']);
    expect(filterStationsByAqiTier(sampleStations, 'poor').map((s) => s.name)).toEqual(['Poor Station']);
    expect(filterStationsByAqiTier(sampleStations, 'severe').map((s) => s.name)).toEqual(['Severe Station']);
  });

  it('wires temporalStep genuinely to timestamp spacing without overclaiming horizons', () => {
    const baseMs = Date.UTC(2026, 10, 27, 0, 0, 0);
    const makeForecastPoint = (offsetHours: number, aqi: number | null = 40 + offsetHours): HourlyTrendPoint => ({
      time: new Date(baseMs + offsetHours * 3600 * 1000).toISOString(),
      pm25: aqi !== null ? 10 + offsetHours : null,
      pm10: null,
      no2: null,
      o3: null,
      us_aqi: aqi,
      is_forecast: true,
      type: 'forecast',
    });

    const forecast72: HourlyTrendPoint[] = Array.from({ length: 72 }, (_, idx) => makeForecastPoint(idx));

    // Full 24 contiguous hourly points span 23 elapsed hours (avoid calling 24 obs a "24h" elapsed horizon)
    const hourly = selectTemporalTimelinePoints(forecast72, 'hourly');
    expect(hourly.points).toHaveLength(24);
    expect(hourly.label).toBe('Hourly Forecast (24 pts, 23h span)');

    // Daily snapshots retain explicit "Snapshots" distinction without false 72h claim (0h, +24h, +48h = 48h span)
    const daily = selectTemporalTimelinePoints(forecast72, 'daily');
    expect(daily.points).toHaveLength(3);
    expect(daily.points.map((p) => p.us_aqi)).toEqual([40, 64, 88]);
    expect(daily.label).toContain('Snapshots');
    expect(daily.label).not.toContain('72h');
    expect(daily.label).toContain('48h span');

    // 72h slice of 72 hourly points has timestamps from +0h to +69h (69h span), never overclaiming 72h
    const horizon69 = selectTemporalTimelinePoints(forecast72, '72h');
    expect(horizon69.points).toHaveLength(24);
    expect(horizon69.points[0].us_aqi).toBe(40);
    expect(horizon69.points[23].us_aqi).toBe(40 + 69);
    expect(horizon69.label).toBe('69h Forecast Trajectory (3h Step)');

    // Full 72h timestamp coverage IS established when timestamps span >= 72h
    const forecastSpanning72 = Array.from({ length: 19 }, (_, idx) => makeForecastPoint(idx * 4)); // 0h..72h
    const full72 = selectTemporalTimelinePoints(forecastSpanning72, '72h');
    expect(full72.label).toContain('72h Forecast Trajectory');

    // Short forecast horizons (< 24h and < 72h) describe actual observation count & elapsed span
    const shortHourly = Array.from({ length: 6 }, (_, idx) => makeForecastPoint(idx));
    expect(selectTemporalTimelinePoints(shortHourly, 'hourly').label).toBe('Hourly Forecast (6 pts, 5h span)');
    expect(selectTemporalTimelinePoints(shortHourly, 'daily').label).toBe('Daily Forecast Snapshot (Single point)');
    expect(selectTemporalTimelinePoints(shortHourly, '72h').label).toBe('3h Forecast Trajectory (3h Step)');

    // Irregular timestamp spacing (missing hours) is detected via timestamps, not indices
    const irregularForecast = [
      makeForecastPoint(0, 40),
      makeForecastPoint(1, 45),
      makeForecastPoint(5, 55),
      makeForecastPoint(26, 60),
    ];
    expect(selectTemporalTimelinePoints(irregularForecast, 'hourly').label).toContain('gaps detected');
    expect(selectTemporalTimelinePoints(irregularForecast, '72h').label).toContain('Irregular / Partial Step');
    expect(selectTemporalTimelinePoints(irregularForecast, 'daily').points).toHaveLength(2);
    expect(selectTemporalTimelinePoints(irregularForecast, 'daily').label).toBe('Daily Forecast Snapshots (2 pts, 26h span)');

    // Empty or all-null forecast arrays report unavailable across all steps
    expect(selectTemporalTimelinePoints([], 'hourly').label).toBe('Forecast Unavailable');
    expect(selectTemporalTimelinePoints([], 'daily').label).toBe('Daily Snapshots Unavailable');
    expect(selectTemporalTimelinePoints(null, '72h').label).toBe('Forecast Unavailable');
    const allNullForecast = Array.from({ length: 24 }, (_, idx) => makeForecastPoint(idx, null));
    expect(selectTemporalTimelinePoints(allNullForecast, 'hourly').label).toBe('Forecast Unavailable');
  });

  it('sorts unsorted timestamps, deduplicates timestamps deterministically, and handles invalid timestamps', () => {
    const baseMs = Date.UTC(2026, 10, 27, 0, 0, 0);
    const makePoint = (offsetHours: number | string, aqi: number | null, pm25: number | null = null): HourlyTrendPoint => ({
      time:
        typeof offsetHours === 'number'
          ? new Date(baseMs + offsetHours * 3600 * 1000).toISOString()
          : offsetHours,
      pm25,
      pm10: null,
      no2: null,
      o3: null,
      us_aqi: aqi,
      is_forecast: true,
      type: 'forecast',
    });

    // 1. Unsorted timestamps: earlier points appearing later must not be dropped and output must be sorted
    const unsorted = [
      makePoint(3, 53),
      makePoint(0, 40),
      makePoint(2, 48),
      makePoint(1, 44),
      makePoint(24, 70),
      makePoint(48, 80),
    ];
    const hourlySorted = selectTemporalTimelinePoints(unsorted, 'hourly');
    expect(hourlySorted.points.map((p) => p.us_aqi)).toEqual([40, 44, 48, 53]);
    expect(hourlySorted.label).toBe('Hourly Forecast (4 pts, 3h span)');

    const dailySorted = selectTemporalTimelinePoints(unsorted, 'daily');
    expect(dailySorted.points.map((p) => p.us_aqi)).toEqual([40, 70, 80]);
    expect(dailySorted.label).toBe('Daily Forecast Snapshots (3 pts, 48h span)');

    const trajSorted = selectTemporalTimelinePoints(unsorted, '72h');
    expect(trajSorted.points.map((p) => p.us_aqi)).toEqual([40, 53, 70, 80]);
    expect(trajSorted.label).toBe('48h Forecast Trajectory (Irregular / Partial Step)');

    // 2. Duplicate timestamps:
    //    - t=0h: null first, valid second (aqi 42) -> prefer valid entry (42)
    //    - t=1h: multiple valid entries (aqi 55 then 99) -> keep first valid entry (55)
    //    - t=2h: multiple missing entries -> retain single unavailable entry without consuming extra slots
    //    - t=3h: valid (aqi 65)
    const duplicates: HourlyTrendPoint[] = [
      makePoint(0, null, null),
      makePoint(0, 42, 12),
      makePoint(1, 55, 16),
      makePoint(1, 99, 30),
      makePoint(2, null, null),
      makePoint(2, null, null),
      makePoint(3, 65, 20),
    ];
    const dedupHourly = selectTemporalTimelinePoints(duplicates, 'hourly');
    expect(dedupHourly.points).toHaveLength(4);
    expect(dedupHourly.points.map((p) => p.us_aqi)).toEqual([42, 55, null, 65]);
    expect(dedupHourly.label).toBe('Hourly Forecast (3 valid pts, 3h span, gaps detected)');

    const dedup72 = selectTemporalTimelinePoints(duplicates, '72h');
    expect(dedup72.points.map((p) => p.us_aqi)).toEqual([42, 65]);
    expect(dedup72.label).toBe('3h Forecast Trajectory (3h Step)');

    // 3. Duplicate timestamps must not crowd out valid hours within 24-point hourly cap
    const crowdedWithDuplicates = [
      ...Array.from({ length: 10 }, () => makePoint(0, null, null)),
      ...Array.from({ length: 24 }, (_, h) => makePoint(h, 40 + h)),
    ];
    const uncapped24 = selectTemporalTimelinePoints(crowdedWithDuplicates, 'hourly');
    expect(uncapped24.points).toHaveLength(24);
    expect(uncapped24.points[0].us_aqi).toBe(40);
    expect(uncapped24.points[23].us_aqi).toBe(63);
    expect(uncapped24.label).toBe('Hourly Forecast (24 pts, 23h span)');

    // 4. All-invalid timestamp strings & mixed valid + invalid timestamp arrays
    const allInvalidTimestamps = [makePoint('not-a-date', 50), makePoint('invalid-ts', 60)];
    const invalidRes = selectTemporalTimelinePoints(allInvalidTimestamps, 'hourly');
    expect(invalidRes.points).toHaveLength(2);
    expect(invalidRes.label).toBe('Forecast (2 valid pts, unverified timestamps)');

    const allInvalidMissingAqi = [makePoint('not-a-date', null), makePoint('', null)];
    expect(selectTemporalTimelinePoints(allInvalidMissingAqi, 'hourly').label).toBe('Forecast Unavailable');

    const mixedTimestamps = [
      makePoint('not-a-date', 99),
      makePoint(1, 45),
      makePoint('bad-ts', 88),
      makePoint(0, 40),
    ];
    const mixedRes = selectTemporalTimelinePoints(mixedTimestamps, 'hourly');
    expect(mixedRes.points.map((p) => p.us_aqi)).toEqual([40, 45]);
    expect(mixedRes.label).toBe('Hourly Forecast (2 pts, 1h span)');
  });

  it('classifies observationMode and forecastStatus strictly from valid measurements and resolvable AQI', () => {
    const emptySummary = buildMapTelemetrySummary(null);
    expect(emptySummary).toEqual({
      dominantPollutant: 'Unavailable',
      observationMode: 'Unavailable',
      forecastStatus: 'Unavailable',
    });

    const baseAq: AirQualityResponse = {
      location: { name: 'Delhi', latitude: 28.6, longitude: 77.2, timezone: 'UTC' },
      measurements: {},
      aqi_standard_results: {},
      dominant_pollutant: null,
      hourly_history: [],
      forecast: [],
      primary_source: 'Open-Meteo CAMS Ensemble (Model Current Estimate)',
      data_freshness_minutes: 5,
      is_ground_observation: false,
    };

    const makeMeas = (
      value: number | null,
      measurement_type: NormalizedMeasurement['measurement_type']
    ): NormalizedMeasurement => ({
      pollutant: 'pm25',
      value,
      unit: 'ug/m3',
      measurement_type,
      source: 'Test Source',
      data_quality: 'verified',
      observation_timestamp: '2026-11-27T00:00:00Z',
      retrieval_timestamp: '2026-11-27T00:00:00Z',
    });

    // Empty measurements & is_ground_observation=false must NOT infer "Model Estimate"
    expect(buildMapTelemetrySummary(baseAq)).toEqual({
      dominantPollutant: 'Unavailable',
      observationMode: 'Unavailable',
      forecastStatus: 'Unavailable',
    });

    // Null, undefined, NaN, Infinity, non-numeric measurements remain Unavailable
    const invalidMeasAq: AirQualityResponse = {
      ...baseAq,
      measurements: {
        pm25: makeMeas(null, 'model_estimate'),
        pm10: makeMeas(Number.NaN, 'ground_observation'),
        no2: makeMeas(Number.POSITIVE_INFINITY, 'model_estimate'),
        o3: { ...makeMeas(null, 'model_estimate'), value: '25' as unknown as number },
      },
      forecast: [
        { time: '2026-11-27T01:00:00Z', pm25: null, pm10: null, no2: null, o3: null, us_aqi: null, is_forecast: true, type: 'forecast' },
      ],
    };
    expect(buildMapTelemetrySummary(invalidMeasAq)).toEqual({
      dominantPollutant: 'Unavailable',
      observationMode: 'Unavailable',
      forecastStatus: 'Unavailable',
    });

    // Genuine 0 ground observation -> Ground Sensor; mixed null + valid forecast -> Active
    const validGroundZeroAq: AirQualityResponse = {
      ...baseAq,
      is_ground_observation: true,
      dominant_pollutant: 'PM25',
      measurements: {
        pm25: makeMeas(0, 'ground_observation'),
      },
      forecast: [
        { time: '2026-11-27T01:00:00Z', pm25: null, us_aqi: null, is_forecast: true, type: 'forecast' },
        { time: '2026-11-27T02:00:00Z', pm25: null, us_aqi: 0, is_forecast: true, type: 'forecast' },
      ],
    };
    expect(buildMapTelemetrySummary(validGroundZeroAq)).toEqual({
      dominantPollutant: 'PM25',
      observationMode: 'Ground Sensor',
      forecastStatus: 'Active',
    });

    // Genuine 0 model estimate -> Model Estimate; pm25-only forecast resolves AQI cleanly -> Active
    const validModelZeroAq: AirQualityResponse = {
      ...baseAq,
      is_ground_observation: false,
      dominant_pollutant: 'PM25',
      measurements: {
        pm25: makeMeas(0, 'model_estimate'),
      },
      forecast: [
        { time: '2026-11-27T01:00:00Z', pm25: 10, us_aqi: null, is_forecast: true, type: 'forecast' },
      ],
    };
    expect(buildMapTelemetrySummary(validModelZeroAq)).toEqual({
      dominantPollutant: 'PM25',
      observationMode: 'Model Estimate',
      forecastStatus: 'Active',
    });
  });

  it('removes dead controls/claims and ensures all referenced Tailwind utility classes are defined', () => {
    const srcRoot = path.resolve(__dirname, '..');
    const mapSource = fs.readFileSync(path.join(srcRoot, 'components/map/GlobalPollutionMap.tsx'), 'utf8');
    const aqiCardSource = fs.readFileSync(path.join(srcRoot, 'components/dashboard/AQIScoreCard.tsx'), 'utf8');
    const gridSource = fs.readFileSync(path.join(srcRoot, 'components/dashboard/PollutantGrid.tsx'), 'utf8');
    const cssSource = fs.readFileSync(path.join(srcRoot, 'index.css'), 'utf8');
    const tailwindConfigSource = fs.readFileSync(path.resolve(srcRoot, '../tailwind.config.js'), 'utf8');

    for (const removed of ['activeDataset', 'chartMode', 'selectedVariable', 'Normal (3.2 m/s)', 'High (CAMS)']) {
      expect(mapSource).not.toContain(removed);
    }

    expect(tailwindConfigSource).toContain('gridTemplateColumns');
    expect(tailwindConfigSource).toContain("'24': 'repeat(24, minmax(0, 1fr))'");
    expect(cssSource).toContain('.scrollbar-none');
    expect(aqiCardSource).not.toContain('card-metric');
    expect(aqiCardSource).not.toContain('terminal-border');
    expect(gridSource).not.toContain('card-metric');
  });
});
