import { HourlyTrendPoint } from '../types/airQuality';

export type PollutantSeriesKey = 'pm25' | 'pm10' | 'no2' | 'o3';

export interface WhoGuidelineBenchmark {
  whoLimit: number;
  name: string;
  formula: string;
  unit: string;
  period: string;
}

/**
 * WHO 2021 24-hr / 8-hr reference guideline benchmarks.
 */
export const WHO_GUIDELINES: Record<string, WhoGuidelineBenchmark> = {
  pm25: { whoLimit: 15, name: 'Fine Particulate Matter', formula: 'PM2.5', unit: 'µg/m³', period: '24h mean' },
  pm10: { whoLimit: 45, name: 'Coarse Particulate Matter', formula: 'PM10', unit: 'µg/m³', period: '24h mean' },
  no2: { whoLimit: 25, name: 'Nitrogen Dioxide', formula: 'NO₂', unit: 'µg/m³', period: '24h mean' },
  so2: { whoLimit: 40, name: 'Sulphur Dioxide', formula: 'SO₂', unit: 'µg/m³', period: '24h mean' },
  co: { whoLimit: 4, name: 'Carbon Monoxide', formula: 'CO', unit: 'mg/m³', period: '24h mean' },
  o3: { whoLimit: 100, name: 'Tropospheric Ozone', formula: 'O₃', unit: 'µg/m³', period: '8h peak' },
};

/**
 * Calculates ratio of measured pollutant concentration to WHO guideline threshold.
 * Returns null for non-finite, missing, or negative concentrations.
 */
export function calculatePollutantExposureRatio(
  pollutant: string,
  concentration: number | null | undefined
): number | null {
  if (typeof concentration !== 'number' || !Number.isFinite(concentration) || concentration < 0) {
    return null;
  }
  const benchmark = WHO_GUIDELINES[pollutant.toLowerCase()];
  if (!benchmark || benchmark.whoLimit <= 0) return 1.0;
  return Number((concentration / benchmark.whoLimit).toFixed(2));
}

/**
 * Unified CliMA Scope 6-band AQI hex color scale used across forecast timelines and spatial pins.
 * Explicitly distinguishes non-finite/missing readings from genuine 0 AQI values.
 */
export function getAqiScaleColor(aqi?: number | null, missingColor: string = '#647570'): string {
  if (typeof aqi !== 'number' || !Number.isFinite(aqi)) return missingColor;
  if (aqi <= 50) return '#23966B';
  if (aqi <= 100) return '#D5A33A';
  if (aqi <= 150) return '#E27C42';
  if (aqi <= 200) return '#C94E55';
  if (aqi <= 300) return '#8E44AD';
  return '#5B2C6F';
}

/**
 * Standard-aware AQI category color mapping matching US EPA (0-500), India CPCB (0-500),
 * and European AQI (0-100 scaled bands) methodologies.
 */
export function getStandardAqiScaleColor(
  aqi?: number | null,
  standard?: string | null,
  missingColor: string = '#647570'
): string {
  if (typeof aqi !== 'number' || !Number.isFinite(aqi) || aqi < 0) return missingColor;
  const norm = typeof standard === 'string' ? standard.trim().toUpperCase() : 'US_EPA';

  if (norm === 'EUROPEAN_AQI') {
    if (aqi <= 10) return '#10b981';
    if (aqi <= 30) return '#22c55e';
    if (aqi <= 50) return '#f59e0b';
    if (aqi <= 70) return '#f97316';
    if (aqi <= 90) return '#ef4444';
    return '#7f1d1d';
  }

  if (norm === 'INDIA_CPCB') {
    if (aqi <= 50) return '#10b981';
    if (aqi <= 100) return '#22c55e';
    if (aqi <= 200) return '#f59e0b';
    if (aqi <= 300) return '#f97316';
    if (aqi <= 400) return '#ef4444';
    return '#7f1d1d';
  }

  return getAqiScaleColor(aqi, missingColor);
}

/**
 * Resolves the verified AQI for an hourly trend point directly from `us_aqi` without
 * fabricating synthetic linear multipliers from PM2.5 when `us_aqi` is unavailable.
 */
export function resolveForecastAqi(item: Pick<HourlyTrendPoint, 'us_aqi' | 'pm25'>): number | null {
  if (typeof item.us_aqi === 'number' && Number.isFinite(item.us_aqi)) {
    return item.us_aqi;
  }
  return null;
}

/**
 * Formats an hourly PM2.5 reading without converting null/undefined/NaN/Infinity into "0 µg".
 */
export function formatHourlyPm25(pm25: number | null | undefined): string {
  if (typeof pm25 === 'number' && Number.isFinite(pm25)) {
    return `${Math.round(pm25)} µg`;
  }
  return '—';
}

export interface SpikeDetectionResult {
  pollutant: PollutantSeriesKey;
  currentVal: number;
  recentAverage: number;
  spikeRatio: number;
}

/**
 * Detects abnormal pollutant concentration spikes using the authoritative AlertService rule:
 * - At least 6 historical records available
 * - Average of recent 6 finite non-null readings > 0
 * - Current concentration >= 1.6x recent 6-hour average AND absolute increase >= 15.0
 */
export function detectConcentrationSpike(
  historyRecords: HourlyTrendPoint[],
  currentVal: number | null | undefined,
  pollutant: PollutantSeriesKey = 'pm25'
): SpikeDetectionResult | null {
  if (
    typeof currentVal !== 'number' ||
    !Number.isFinite(currentVal) ||
    !historyRecords ||
    historyRecords.length < 6
  ) {
    return null;
  }

  const recentVals = historyRecords
    .slice(-6)
    .map((r) => r[pollutant])
    .filter((v): v is number => typeof v === 'number' && Number.isFinite(v));

  if (recentVals.length === 0) return null;

  const avgRecent = recentVals.reduce((sum, v) => sum + v, 0) / recentVals.length;
  if (avgRecent > 0 && currentVal / avgRecent >= 1.6 && currentVal - avgRecent >= 15.0) {
    return {
      pollutant,
      currentVal,
      recentAverage: Number(avgRecent.toFixed(1)),
      spikeRatio: Number((currentVal / avgRecent).toFixed(2)),
    };
  }

  return null;
}

export interface TrajectoryChartPoint {
  time: string;
  isoTime: string;
  observed: number | null;
  forecast: number | null;
  isForecast: boolean;
  isSynthesized?: boolean;
  pm25: number | null;
  pm10: number | null;
  no2: number | null;
  o3: number | null;
}

function toRoundedOrNull(val: unknown): number | null {
  return typeof val === 'number' && Number.isFinite(val) ? Number(val.toFixed(1)) : null;
}

/**
 * Formats a finite numeric value to fixed decimals, returning fallback for null/undefined/NaN/Infinity or non-numbers.
 */
export function formatFiniteDecimal(
  val: unknown,
  decimals: number = 1,
  fallback: string = '—'
): string {
  if (typeof val !== 'number' || !Number.isFinite(val)) {
    return fallback;
  }
  return (Object.is(val, -0) ? 0 : val).toFixed(decimals);
}

export function formatTrajectoryTimeLabel(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleTimeString([], { month: 'numeric', day: 'numeric', hour: '2-digit' });
  } catch {
    return isoString;
  }
}

/**
 * Maps historical and forecast telemetry into Recharts-ready contiguous trajectory series
 * by bridging the final historical observation cleanly into the forecast curve.
 */
export function buildTrajectorySeries(
  rawHistory: HourlyTrendPoint[],
  rawForecast: HourlyTrendPoint[],
  selectedPollutant: PollutantSeriesKey
): {
  historySeries: TrajectoryChartPoint[];
  forecastSeries: TrajectoryChartPoint[];
  combinedTrajectory: TrajectoryChartPoint[];
} {
  const historySeries: TrajectoryChartPoint[] = rawHistory.map((pt) => ({
    time: formatTrajectoryTimeLabel(pt.time),
    isoTime: pt.time,
    observed: toRoundedOrNull(pt[selectedPollutant]),
    forecast: null,
    isForecast: false,
    isSynthesized: Boolean(pt.is_synthesized) || pt.type === 'ground_anchored_reanalysis',
    pm25: toRoundedOrNull(pt.pm25),
    pm10: toRoundedOrNull(pt.pm10),
    no2: toRoundedOrNull(pt.no2),
    o3: toRoundedOrNull(pt.o3),
  }));

  const forecastSeries: TrajectoryChartPoint[] = rawForecast.slice(0, 24).map((pt) => ({
    time: formatTrajectoryTimeLabel(pt.time),
    isoTime: pt.time,
    observed: null,
    forecast: toRoundedOrNull(pt[selectedPollutant]),
    isForecast: true,
    isSynthesized: Boolean(pt.is_synthesized) || pt.type === 'ground_anchored_reanalysis',
    pm25: toRoundedOrNull(pt.pm25),
    pm10: toRoundedOrNull(pt.pm10),
    no2: toRoundedOrNull(pt.no2),
    o3: toRoundedOrNull(pt.o3),
  }));

  let combinedTrajectory: TrajectoryChartPoint[] = [];
  if (historySeries.length > 0 && forecastSeries.length > 0) {
    const lastHistory = historySeries[historySeries.length - 1];
    const bridgePoint: TrajectoryChartPoint = {
      ...lastHistory,
      forecast: lastHistory.observed,
    };
    combinedTrajectory = [...historySeries.slice(0, -1), bridgePoint, ...forecastSeries];
  } else if (historySeries.length > 0) {
    combinedTrajectory = [...historySeries];
  } else if (forecastSeries.length > 0) {
    combinedTrajectory = [...forecastSeries];
  }

  return { historySeries, forecastSeries, combinedTrajectory };
}

export function hasValidTrajectoryData(series: TrajectoryChartPoint[]): boolean {
  return series.some(
    (d) =>
      (typeof d.observed === 'number' && Number.isFinite(d.observed)) ||
      (typeof d.forecast === 'number' && Number.isFinite(d.forecast))
  );
}

/**
 * Selects up to 18 recent observed hourly bars (or next 18 forecast bars when history is absent).
 */
export function selectChartBDistribution(
  historySeries: TrajectoryChartPoint[],
  forecastSeries: TrajectoryChartPoint[]
): TrajectoryChartPoint[] {
  if (historySeries.length > 0) {
    return historySeries.slice(-18);
  }
  if (forecastSeries.length > 0) {
    return forecastSeries.slice(0, 18);
  }
  return [];
}

/**
 * Neutralizes untrusted text cells against spreadsheet formula injection before RFC 4180 quoting.
 * Checks both direct formula-leading triggers (=, +, -, @, \t, \r) and leading ASCII whitespace/control
 * prefixes followed by (=, +, -, @) to block simple evasion, while preserving numeric columns separately.
 */
function formatCsvTextCell(raw: unknown): string {
  const str = raw == null ? '' : String(raw);
  const trimmedLeading = str.replace(/^[\u0000-\u0020]+/, '');
  const isFormulaRisk =
    /^[=+\-@\t\r]/.test(str) || (/^[\u0000-\u0020]/.test(str) && /^[=+\-@]/.test(trimmedLeading));
  const neutralized = isFormulaRisk ? `'${str}` : str;
  return `"${neutralized.replace(/"/g, '""')}"`;
}

function formatCsvNumberCell(val: unknown): string {
  if (typeof val === 'number' && Number.isFinite(val)) {
    return Object.is(val, -0) ? '0' : String(val);
  }
  return '';
}

/**
 * Derives a safe download filename by stripping control chars, path separators, traversal dots,
 * and unsafe punctuation, falling back cleanly when empty and preserving the requested extension.
 */
export function sanitizeDownloadFilename(
  rawName: string,
  extension: string = '.csv',
  fallbackBase: string = 'AeroSense_Export'
): string {
  const normalizedExt = extension ? (extension.startsWith('.') ? extension : `.${extension}`) : '';
  const cleanPart = (input: string): string => {
    let stem = String(input ?? '');
    if (normalizedExt && stem.toLowerCase().endsWith(normalizedExt.toLowerCase())) {
      stem = stem.slice(0, -normalizedExt.length);
    }
    return stem
      .replace(/\.{2,}/g, '_')
      .replace(/[^A-Za-z0-9._-]+/g, '_')
      .replace(/_+/g, '_')
      .replace(/^[._]+|[._]+$/g, '');
  };

  const safeStem = cleanPart(rawName) || cleanPart(fallbackBase) || 'export';
  return `${safeStem}${normalizedExt}`;
}

/**
 * Builds an RFC 4180 compliant trajectory CSV with UTF-8 BOM, CRLF line endings,
 * separate numeric/text cell handling, and spreadsheet formula neutralization.
 */
export function buildTrajectoryCsv(
  trajectory: TrajectoryChartPoint[],
  pollutantLabel: string,
  unit: string
): string {
  const headers = 'Timestamp,Pollutant,Observed_Conc,Forecast_Conc,Unit,Type';
  const rows = trajectory.map((s) =>
    [
      formatCsvTextCell(s.isoTime || s.time),
      formatCsvTextCell(pollutantLabel),
      formatCsvNumberCell(s.observed),
      formatCsvNumberCell(s.forecast),
      formatCsvTextCell(unit),
      formatCsvTextCell(
        s.isForecast
          ? s.isSynthesized
            ? 'Forecast (Diurnal Projection)'
            : 'Forecast'
          : s.isSynthesized
          ? 'Model-Derived Diurnal Projection'
          : 'Observed'
      ),
    ].join(',')
  );
  return `\uFEFF${[headers, ...rows].join('\r\n')}`;
}
