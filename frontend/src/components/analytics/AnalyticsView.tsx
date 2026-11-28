import React, { useState, useMemo } from 'react';
import { useAQI } from '../../context/AQIContext';
import { useTheme } from '../../context/ThemeContext';
import {
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
  ComposedChart
} from 'recharts';
import { LineChart, AlertTriangle, Activity, Zap, Download, RefreshCw, Info } from 'lucide-react';
import {
  buildTrajectoryCsv,
  buildTrajectorySeries,
  detectConcentrationSpike,
  formatFiniteDecimal,
  hasValidTrajectoryData,
  sanitizeDownloadFilename,
  selectChartBDistribution,
} from '../../utils/airQualityHelpers';

const pollutantMeta: Record<'pm25' | 'pm10' | 'no2' | 'o3', { label: string; full: string; unit: string; color: string }> = {
  o3: { label: 'O₃', full: 'Ground-Level Ozone (O₃)', unit: 'µg/m³', color: '#8E44AD' },
  pm25: { label: 'PM2.5', full: 'Fine Particulate Matter (PM2.5)', unit: 'µg/m³', color: '#087F72' },
  pm10: { label: 'PM10', full: 'Coarse Particulate Matter (PM10)', unit: 'µg/m³', color: '#159DB0' },
  no2: { label: 'NO₂', full: 'Nitrogen Dioxide (NO₂)', unit: 'µg/m³', color: '#D5A33A' },
};

export const AnalyticsView: React.FC = () => {
  const { airQuality, activeCity, loading, error, refreshData } = useAQI();
  const { resolvedTheme } = useTheme();
  const [selectedPollutant, setSelectedPollutant] = useState<'o3' | 'pm25' | 'pm10' | 'no2'>('o3');
  const [timeRange, setTimeRange] = useState<'24h' | '48h' | '72h'>('72h');

  const isDark = resolvedTheme === 'dark';

  // Process raw hourly history and forecast data
  const rawHistory = useMemo(() => airQuality?.hourly_history || [], [airQuality]);
  const rawForecast = useMemo(() => airQuality?.forecast || [], [airQuality]);

  const hasHistory = rawHistory.length > 0;
  const hasForecast = rawForecast.length > 0;
  const isSynthesizedHistory = useMemo(
    () => rawHistory.some((pt) => Boolean(pt?.is_synthesized) || pt?.type === 'ground_anchored_reanalysis'),
    [rawHistory]
  );

  // Transform historical, forecast, and bridged trajectory points via shared helper
  const { historySeries, forecastSeries, combinedTrajectory } = useMemo(
    () => buildTrajectorySeries(rawHistory, rawForecast, selectedPollutant),
    [rawHistory, rawForecast, selectedPollutant]
  );

  const displayedTrajectory = useMemo(() => {
    if (timeRange === '24h') {
      if (historySeries.length > 0 && forecastSeries.length > 0) {
        const recentHistory = historySeries.slice(-12);
        const upcomingForecast = forecastSeries.slice(0, 12);
        const lastHist = recentHistory[recentHistory.length - 1];
        const bridge = { ...lastHist, forecast: lastHist.observed };
        return [...recentHistory.slice(0, -1), bridge, ...upcomingForecast];
      }
      return combinedTrajectory.slice(-24);
    }
    if (timeRange === '48h') return combinedTrajectory.slice(-48);
    return combinedTrajectory;
  }, [historySeries, forecastSeries, combinedTrajectory, timeRange]);

  const hasValidChartAData = useMemo(
    () => hasValidTrajectoryData(displayedTrajectory),
    [displayedTrajectory]
  );

  // Multi-pollutant distribution data (Chart B): prioritize recent 18 hours of observations
  const chartBData = useMemo(
    () => selectChartBDistribution(historySeries, forecastSeries),
    [historySeries, forecastSeries]
  );

  const hasValidChartBData = useMemo(() => {
    return chartBData.some(
      (d) => d.pm25 !== null || d.pm10 !== null || d.no2 !== null
    );
  }, [chartBData]);

  const chartBPeriodLabel = hasHistory
    ? isSynthesizedHistory
      ? 'Recent 18 Hours (Diurnal Projection — CAMS Offline)'
      : 'Recent 18 Hours (CAMS History & Observations)'
    : hasForecast
    ? 'Next 18 Hours (Atmospheric Forecast)'
    : 'Recent 18 Hours';

  // Current metric readings
  const meta = pollutantMeta[selectedPollutant];
  const rawMeasurement = airQuality?.measurements?.[selectedPollutant];
  const currentVal = formatFiniteDecimal(rawMeasurement?.value, 1, '—');
  const rawUnit = rawMeasurement?.unit;
  const seriesUnit = meta.unit;
  const currentUnit =
    rawUnit && !['aqi_subindex', 'waqi_iaqi_subindex', 'ppm', 'ppb', 'unavailable'].includes(rawUnit)
      ? rawUnit
      : meta.unit;
  const currentSource = rawMeasurement?.source || airQuality?.primary_source || 'Station Telemetry';

  // Spike detection unified with backend AlertService.detect_spike (>= 1.6x ratio and >= 15.0 delta over 6h mean)
  const spikeResult = useMemo(
    () => detectConcentrationSpike(rawHistory, rawMeasurement?.value, selectedPollutant),
    [rawHistory, rawMeasurement?.value, selectedPollutant]
  );

  // Export CSV handler
  const handleExportCSV = () => {
    if (!hasValidChartAData) return;
    const csvContent = buildTrajectoryCsv(displayedTrajectory, meta.label, seriesUnit);
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const safeCity = sanitizeDownloadFilename(activeCity.name, '', 'location');
    a.href = url;
    a.download = sanitizeDownloadFilename(
      `AeroSense_${safeCity}_${selectedPollutant}_Trajectory_${new Date().toISOString().slice(0, 10)}`,
      '.csv'
    );
    a.click();
    URL.revokeObjectURL(url);
  };

  // Loading state
  if (loading && !airQuality) {
    return (
      <div className="space-y-6 max-w-7xl mx-auto pb-12 font-sans animate-pulse">
        <div className="h-16 bg-clima-surface dark:bg-darkClima-surface rounded-xl border border-clima-border dark:border-darkClima-border" />
        <div className="h-96 bg-clima-surface dark:bg-darkClima-surface rounded-xl border border-clima-border dark:border-darkClima-border" />
        <div className="h-80 bg-clima-surface dark:bg-darkClima-surface rounded-xl border border-clima-border dark:border-darkClima-border" />
      </div>
    );
  }

  // Error state
  if (error && !airQuality) {
    return (
      <div className="max-w-7xl mx-auto py-16 px-4 text-center space-y-4">
        <div className="inline-flex p-4 bg-amber-500/10 rounded-full text-amber-500">
          <AlertTriangle className="w-8 h-8" />
        </div>
        <h3 className="text-lg font-bold text-clima-text dark:text-darkClima-text">
          Environmental Telemetry Ingestion Failed
        </h3>
        <p className="text-xs text-clima-muted dark:text-darkClima-muted max-w-md mx-auto">
          {error}
        </p>
        <button
          onClick={() => refreshData()}
          className="inline-flex items-center space-x-2 px-4 py-2 bg-clima-accent dark:bg-darkClima-accent text-white dark:text-darkClima-bg font-semibold text-xs rounded-lg shadow-sm hover:opacity-90 transition-opacity"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry Data Ingestion</span>
        </button>
      </div>
    );
  }

  if (!airQuality) return null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 font-sans">
      {error && (
        <div
          role="alert"
          className="p-3.5 bg-red-500/10 border border-red-500/30 rounded-xl flex items-center justify-between text-xs text-red-700 dark:text-red-300"
        >
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => refreshData()}
            className="px-2.5 py-1 bg-red-500/20 hover:bg-red-500/30 rounded font-medium transition-colors"
          >
            Retry
          </button>
        </div>
      )}
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-clima-border dark:border-darkClima-border pb-5">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-clima-subtle dark:bg-darkClima-subtle rounded-lg text-clima-accent dark:text-darkClima-accent border border-clima-border dark:border-darkClima-border">
              <LineChart className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-clima-text dark:text-darkClima-text tracking-tight font-sans">
                Atmospheric Pollution Analytics & Spatio-Temporal Trends
              </h2>
              <p className="text-xs text-clima-muted dark:text-darkClima-muted mt-0.5">
                Location: <span className="text-clima-text dark:text-darkClima-text font-semibold">{activeCity.name}</span> •{' '}
                {isSynthesizedHistory
                  ? '72h ground-anchored diurnal projection (CAMS reanalysis unavailable).'
                  : '72h contiguous trajectory (48h atmospheric history + 24h CAMS forecast).'}
              </p>
            </div>
          </div>
        </div>

        {/* Controls: Pollutant Tabs, Time Range & Export */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Pollutant Tabs */}
          <div className="flex items-center bg-clima-subtle dark:bg-darkClima-subtle p-1 rounded-lg border border-clima-border dark:border-darkClima-border">
            {(['o3', 'pm25', 'pm10', 'no2'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setSelectedPollutant(p)}
                className={`px-3 py-1.5 text-xs rounded-md transition-colors font-sans ${
                  selectedPollutant === p
                    ? 'bg-clima-surface dark:bg-darkClima-surface text-clima-accent dark:text-darkClima-accent font-semibold shadow-sm'
                    : 'text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text'
                }`}
              >
                {pollutantMeta[p].label}
              </button>
            ))}
          </div>

          {/* Time Range Selector */}
          <div className="flex items-center bg-clima-subtle dark:bg-darkClima-subtle p-1 rounded-lg border border-clima-border dark:border-darkClima-border text-xs">
            {(['24h', '48h', '72h'] as const).map((tr) => (
              <button
                key={tr}
                onClick={() => setTimeRange(tr)}
                className={`px-2.5 py-1 rounded transition-colors font-mono ${
                  timeRange === tr
                    ? 'bg-clima-surface dark:bg-darkClima-surface text-clima-text dark:text-darkClima-text font-bold shadow-sm'
                    : 'text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text'
                }`}
              >
                {tr}
              </button>
            ))}
          </div>

          {/* Export CSV Button */}
          <button
            onClick={handleExportCSV}
            disabled={!hasValidChartAData}
            title="Export Trajectory CSV Data"
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-clima-surface dark:bg-darkClima-surface hover:bg-clima-subtle dark:hover:bg-darkClima-subtle disabled:opacity-40 disabled:cursor-not-allowed border border-clima-border dark:border-darkClima-border text-clima-text dark:text-darkClima-text text-xs rounded-lg shadow-sm transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-clima-accent dark:text-darkClima-accent" />
            <span className="hidden sm:inline">Export CSV</span>
          </button>
        </div>
      </div>

      {/* Degradation Notice Banner (When CAMS forecast is unavailable) */}
      {!hasForecast && (
        <div className="p-3.5 bg-amber-500/10 border border-amber-500/25 rounded-xl flex items-center justify-between text-xs text-amber-800 dark:text-amber-200">
          <div className="flex items-center space-x-2.5">
            <Info className="w-4 h-4 text-amber-500 shrink-0" />
            <span>
              <strong>Copernicus CAMS Forecast Notice:</strong> Model-based 24-hour predictive telemetry is temporarily degraded or rate-limited. Verified historical observations remain fully active.
            </span>
          </div>
          <button
            onClick={() => refreshData()}
            className="flex items-center space-x-1 px-2.5 py-1 text-[11px] font-semibold text-amber-900 dark:text-amber-100 bg-amber-500/20 hover:bg-amber-500/30 rounded transition-colors shrink-0 ml-3"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Refresh</span>
          </button>
        </div>
      )}

      {/* Spike Alert Banner if detected */}
      {spikeResult && (
        <div className="p-4 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/80 rounded-xl flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-amber-100 dark:bg-amber-900/60 rounded-lg text-amber-700 dark:text-amber-300">
              <Zap className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-amber-900 dark:text-amber-200 font-sans">
                Concentration Surge Detected ({meta.label})
              </h4>
              <p className="text-[11px] text-amber-800 dark:text-amber-300/80 font-sans">
                Current reading ({spikeResult.currentVal} {currentUnit}) is {spikeResult.spikeRatio}x above the recent 6-hour baseline ({spikeResult.recentAverage} {currentUnit}).
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Chart A: Main Multi-Period Trajectory Card */}
      <div className="bg-clima-surface dark:bg-darkClima-surface rounded-xl p-5 border border-clima-border dark:border-darkClima-border space-y-4 shadow-floating dark:shadow-floating-dark">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-clima-border dark:border-darkClima-border pb-3.5">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold text-clima-muted dark:text-darkClima-muted uppercase tracking-wider font-sans">
                {meta.label} Concentration Trajectory
              </span>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border text-clima-muted dark:text-darkClima-muted">
                {meta.full}
              </span>
            </div>
            <div className="flex items-baseline space-x-3 mt-1">
              <div className="text-2xl font-bold font-mono text-clima-text dark:text-darkClima-text">
                Current: <span className="text-clima-accent dark:text-darkClima-accent">{currentVal}</span> {currentUnit}
              </div>
              <span className="text-[11px] text-clima-muted dark:text-darkClima-muted truncate max-w-md hidden md:inline">
                {currentSource}
              </span>
            </div>
          </div>

          {/* Legend and Source Status Indicators */}
          <div className="flex flex-wrap items-center gap-3 text-xs font-sans text-clima-muted dark:text-darkClima-muted">
            <span className="flex items-center">
              <span className="w-2.5 h-2.5 rounded-full bg-[#087F72] mr-1.5" />
              <span>{isSynthesizedHistory ? 'Diurnal Projection (Synth.)' : 'Historical Trajectory'}</span>
              {!hasHistory && <span className="ml-1 text-[10px] text-amber-500">(Offline)</span>}
            </span>
            <span className="flex items-center">
              <span className="w-2.5 h-2.5 rounded-full bg-[#159DB0] mr-1.5" />
              <span>Model Forecast</span>
              {!hasForecast && <span className="ml-1 text-[10px] text-amber-500">(Offline)</span>}
            </span>
          </div>
        </div>

        {/* Chart A Canvas or Fallback State */}
        {hasValidChartAData ? (
          <div className="h-80 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%" minWidth={280} minHeight={240}>
              <ComposedChart data={displayedTrajectory} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="observedGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#087F72" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#087F72" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#159DB0" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#159DB0" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#304442' : '#E2E8F0'} />
                <XAxis
                  dataKey="time"
                  stroke={isDark ? '#A1B4AD' : '#647570'}
                  tick={{ fontSize: 10, fill: isDark ? '#A1B4AD' : '#647570', fontFamily: 'monospace' }}
                />
                <YAxis
                  stroke={isDark ? '#A1B4AD' : '#647570'}
                  tick={{ fontSize: 10, fill: isDark ? '#A1B4AD' : '#647570', fontFamily: 'monospace' }}
                  unit={` ${seriesUnit}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: isDark ? '#172426' : '#FFFFFF',
                    borderColor: isDark ? '#304442' : '#DCE5E1',
                    borderRadius: '8px',
                    fontFamily: 'monospace',
                    fontSize: '11px',
                    color: isDark ? '#E8F1EE' : '#172B28',
                    boxShadow: '0 4px 15px rgba(0,0,0,0.1)',
                  }}
                  formatter={(val: number | string | Array<number | string> | undefined, name: string | number): [string, string | number] => {
                    if (typeof val !== 'number' || !Number.isFinite(val)) return ['N/A', name];
                    return [`${val} ${seriesUnit}`, name];
                  }}
                  labelFormatter={(label) => `Time: ${label}`}
                />
                <Area
                  type="monotone"
                  dataKey="observed"
                  name={isSynthesizedHistory ? 'Diurnal Projection (Synth.)' : 'Historical Trajectory'}
                  stroke="#087F72"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#observedGrad)"
                  connectNulls={false}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="forecast"
                  name="Model Forecast"
                  stroke="#159DB0"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-80 w-full flex flex-col items-center justify-center text-center p-6 bg-clima-subtle/30 dark:bg-darkClima-subtle/20 rounded-lg border border-dashed border-clima-border dark:border-darkClima-border space-y-3">
            <div className="p-3 bg-clima-surface dark:bg-darkClima-surface rounded-full text-amber-500 border border-clima-border dark:border-darkClima-border">
              <Activity className="w-6 h-6" />
            </div>
            <div className="max-w-md space-y-1">
              <h4 className="text-sm font-semibold text-clima-text dark:text-darkClima-text font-sans">
                Contiguous Trajectory Telemetry Unavailable
              </h4>
              <p className="text-xs text-clima-muted dark:text-darkClima-muted font-sans leading-relaxed">
                Atmospheric reanalysis and forecast models are currently degraded or rate-limited for {activeCity.name}. The verified real-time reading ({currentVal} {currentUnit}) remains active above.
              </p>
            </div>
            <button
              onClick={() => refreshData()}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium text-clima-accent dark:text-darkClima-accent bg-clima-surface dark:bg-darkClima-surface hover:bg-clima-subtle dark:hover:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-lg transition-colors shadow-sm"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Telemetry Ingestion</span>
            </button>
          </div>
        )}
      </div>

      {/* Chart B: Multi-Pollutant Distribution Card */}
      <div className="bg-clima-surface dark:bg-darkClima-surface rounded-xl p-5 border border-clima-border dark:border-darkClima-border space-y-3 shadow-floating dark:shadow-floating-dark">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-clima-border dark:border-darkClima-border pb-3">
          <div>
            <h3 className="text-xs font-semibold text-clima-text dark:text-darkClima-text uppercase tracking-wider font-sans">
              Multi-Pollutant Hourly Distribution
            </h3>
            <p className="text-[11px] text-clima-muted dark:text-darkClima-muted font-sans mt-0.5">
              {chartBPeriodLabel}
            </p>
          </div>
          <div className="text-[11px] text-clima-muted dark:text-darkClima-muted font-sans">
            Units: <span className="font-mono text-clima-text dark:text-darkClima-text">µg/m³</span>
          </div>
        </div>

        {hasValidChartBData ? (
          <div className="h-64 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%" minWidth={280} minHeight={200}>
              <BarChart data={chartBData} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#304442' : '#E2E8F0'} />
                <XAxis
                  dataKey="time"
                  stroke={isDark ? '#A1B4AD' : '#647570'}
                  tick={{ fontSize: 10, fill: isDark ? '#A1B4AD' : '#647570', fontFamily: 'monospace' }}
                />
                <YAxis
                  stroke={isDark ? '#A1B4AD' : '#647570'}
                  tick={{ fontSize: 10, fill: isDark ? '#A1B4AD' : '#647570', fontFamily: 'monospace' }}
                  unit=" µg/m³"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: isDark ? '#172426' : '#FFFFFF',
                    borderColor: isDark ? '#304442' : '#DCE5E1',
                    borderRadius: '8px',
                    fontFamily: 'monospace',
                    fontSize: '11px',
                    color: isDark ? '#E8F1EE' : '#172B28',
                  }}
                  formatter={(val: number | string | Array<number | string> | undefined, name: string | number): [string, string | number] => [
                    typeof val === 'number' && Number.isFinite(val) ? `${val} µg/m³` : 'Not Monitored',
                    name
                  ]}
                  labelFormatter={(label) => `Time: ${label}`}
                />
                <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'sans-serif' }} />
                <Bar dataKey="pm25" name="PM2.5" fill="#087F72" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                <Bar dataKey="pm10" name="PM10" fill="#159DB0" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                <Bar dataKey="no2" name="NO₂" fill="#D5A33A" radius={[3, 3, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-64 w-full flex flex-col items-center justify-center text-center p-6 bg-clima-subtle/30 dark:bg-darkClima-subtle/20 rounded-lg border border-dashed border-clima-border dark:border-darkClima-border space-y-2">
            <Activity className="w-5 h-5 text-amber-500" />
            <h4 className="text-xs font-semibold text-clima-text dark:text-darkClima-text font-sans">
              Hourly Multi-Pollutant Series Unavailable
            </h4>
            <p className="text-[11px] text-clima-muted dark:text-darkClima-muted font-sans max-w-sm">
              Copernicus atmospheric model estimates are currently unavailable. Verified ground observations for PM2.5 and PM10 remain active in the primary dashboard.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
