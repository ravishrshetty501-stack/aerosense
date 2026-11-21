import React, { useState } from 'react';
import { useAQI } from '../../context/AQIContext';
import { useTheme } from '../../context/ThemeContext';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend
} from 'recharts';
import { LineChart, AlertTriangle, Calendar, Activity, Zap, Download, Filter } from 'lucide-react';

export const AnalyticsView: React.FC = () => {
  const { airQuality, activeCity, standard } = useAQI();
  const { theme } = useTheme();
  const [selectedPollutant, setSelectedPollutant] = useState<'pm25' | 'pm10' | 'no2' | 'o3'>('pm25');
  const [timeRange, setTimeRange] = useState<'24h' | '48h' | '72h'>('72h');

  if (!airQuality) return null;

  const isDark = theme === 'dark';

  // Past 48h history and 24h forecast
  const historySeries = (airQuality.hourly_history || []).map((pt) => ({
    time: new Date(pt.time).toLocaleTimeString([], { month: 'numeric', day: 'numeric', hour: '2-digit' }),
    pm25: pt.pm25,
    pm10: pt.pm10,
    no2: pt.no2,
    o3: pt.o3,
    aqi: pt.us_aqi,
    isForecast: false,
  }));

  const forecastSeries = (airQuality.forecast || []).slice(0, 24).map((pt) => ({
    time: new Date(pt.time).toLocaleTimeString([], { month: 'numeric', day: 'numeric', hour: '2-digit' }),
    pm25: pt.pm25,
    pm10: pt.pm10,
    no2: pt.no2,
    o3: pt.o3,
    aqi: pt.us_aqi,
    isForecast: true,
  }));

  const combinedSeries = [...historySeries, ...forecastSeries];
  const displayedSeries = timeRange === '24h' ? combinedSeries.slice(-24) : timeRange === '48h' ? combinedSeries.slice(-48) : combinedSeries;

  const pollutantColors = {
    pm25: '#087F72',
    pm10: '#159DB0',
    no2: '#D5A33A',
    o3: '#8E44AD',
  };

  const currentVal = airQuality.measurements[selectedPollutant]?.value ?? '—';

  // Spike detection
  const recentVals = historySeries.slice(-6).map((h) => h[selectedPollutant]).filter((v) => typeof v === 'number');
  const priorVals = historySeries.slice(-12, -6).map((h) => h[selectedPollutant]).filter((v) => typeof v === 'number');
  const recentAvg = recentVals.length > 0 ? recentVals.reduce((a, b) => a + b, 0) / recentVals.length : 0;
  const priorAvg = priorVals.length > 0 ? priorVals.reduce((a, b) => a + b, 0) / priorVals.length : 0;
  const spikeDetected = priorAvg > 0 && recentAvg > priorAvg * 1.35;

  // Export CSV
  const handleExportCSV = () => {
    const headers = 'Time,PM2.5,PM10,NO2,O3,Type\n';
    const rows = displayedSeries.map(s => `"${s.time}",${s.pm25 ?? ''},${s.pm10 ?? ''},${s.no2 ?? ''},${s.o3 ?? ''},${s.isForecast ? 'Forecast' : 'Observed'}`).join('\n');
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `AeroSense_${activeCity.name}_${selectedPollutant}_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 font-sans">
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
                Location: <span className="text-clima-text dark:text-darkClima-text font-semibold">{activeCity.name}</span> • 72h contiguous reanalysis (48h verified history + 24h CAMS atmospheric forecast).
              </p>
            </div>
          </div>
        </div>

        {/* Controls: Pollutant Tabs & Export */}
        <div className="flex items-center space-x-2">
          {/* Pollutant Tabs */}
          <div className="flex items-center bg-clima-subtle dark:bg-darkClima-subtle p-1 rounded-lg border border-clima-border dark:border-darkClima-border">
            {(['pm25', 'pm10', 'no2', 'o3'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setSelectedPollutant(p)}
                className={`px-3 py-1.5 text-xs rounded-md transition-colors font-sans ${
                  selectedPollutant === p
                    ? 'bg-clima-surface dark:bg-darkClima-surface text-clima-accent dark:text-darkClima-accent font-semibold shadow-sm'
                    : 'text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text'
                }`}
              >
                {p.toUpperCase()}
              </button>
            ))}
          </div>

          {/* Export CSV Button */}
          <button
            onClick={handleExportCSV}
            title="Export CSV Data"
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-clima-surface dark:bg-darkClima-surface hover:bg-clima-subtle dark:hover:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border text-clima-text dark:text-darkClima-text text-xs rounded-lg shadow-sm transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-clima-accent dark:text-darkClima-accent" />
            <span className="hidden sm:inline">Export CSV</span>
          </button>
        </div>
      </div>

      {/* Spike Alert Banner if detected */}
      {spikeDetected && (
        <div className="p-4 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/80 rounded-xl flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-amber-100 dark:bg-amber-900/60 rounded-lg text-amber-700 dark:text-amber-300">
              <Zap className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-amber-900 dark:text-amber-200 font-sans">
                Particulate Concentration Surge Detected ({selectedPollutant.toUpperCase()})
              </h4>
              <p className="text-[11px] text-amber-800 dark:text-amber-300/80 font-sans">
                Recent 6-hour average ({recentAvg.toFixed(1)} µg/m³) is {Math.round(((recentAvg - priorAvg) / priorAvg) * 100)}% higher than the preceding baseline ({priorAvg.toFixed(1)} µg/m³).
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Main Multi-Period Chart Card */}
      <div className="bg-clima-surface dark:bg-darkClima-surface rounded-xl p-5 border border-clima-border dark:border-darkClima-border space-y-4 shadow-floating dark:shadow-floating-dark">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-clima-border dark:border-darkClima-border pb-3">
          <div>
            <span className="text-xs font-semibold text-clima-muted dark:text-darkClima-muted uppercase tracking-wider font-sans">
              {selectedPollutant.toUpperCase()} Concentration Trajectory
            </span>
            <div className="text-2xl font-bold font-mono text-clima-text dark:text-darkClima-text mt-0.5">
              Current: <span className="text-clima-accent dark:text-darkClima-accent">{currentVal}</span> µg/m³
            </div>
          </div>

          <div className="flex items-center space-x-4 text-xs font-sans text-clima-muted dark:text-darkClima-muted">
            <span className="flex items-center">
              <span className="w-3 h-3 rounded-full bg-[#087F72] mr-1.5 opacity-90" /> Observed History
            </span>
            <span className="flex items-center">
              <span className="w-3 h-3 rounded-full bg-[#159DB0] mr-1.5 opacity-90" /> Model Forecast
            </span>
          </div>
        </div>

        <div className="h-80 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={displayedSeries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="pollutantGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={pollutantColors[selectedPollutant]} stopOpacity={0.35} />
                  <stop offset="95%" stopColor={pollutantColors[selectedPollutant]} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#304442' : '#E2E8F0'} />
              <XAxis dataKey="time" stroke={isDark ? '#A1B4AD' : '#647570'} tick={{ fontSize: 10, fill: isDark ? '#A1B4AD' : '#647570', fontFamily: 'monospace' }} />
              <YAxis stroke={isDark ? '#A1B4AD' : '#647570'} tick={{ fontSize: 10, fill: isDark ? '#A1B4AD' : '#647570', fontFamily: 'monospace' }} />
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
              />
              <Area
                type="monotone"
                dataKey={selectedPollutant}
                stroke={pollutantColors[selectedPollutant]}
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#pollutantGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Multi-Pollutant Distribution */}
      <div className="bg-clima-surface dark:bg-darkClima-surface rounded-xl p-5 border border-clima-border dark:border-darkClima-border space-y-3 shadow-floating dark:shadow-floating-dark">
        <h3 className="text-xs font-semibold text-clima-text dark:text-darkClima-text uppercase tracking-wider font-sans">
          Multi-Pollutant Hourly Distribution (Recent 18 Hours)
        </h3>
        <div className="h-64 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={displayedSeries.slice(-18)} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#304442' : '#E2E8F0'} />
              <XAxis dataKey="time" stroke={isDark ? '#A1B4AD' : '#647570'} tick={{ fontSize: 10, fill: isDark ? '#A1B4AD' : '#647570', fontFamily: 'monospace' }} />
              <YAxis stroke={isDark ? '#A1B4AD' : '#647570'} tick={{ fontSize: 10, fill: isDark ? '#A1B4AD' : '#647570', fontFamily: 'monospace' }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: isDark ? '#172426' : '#FFFFFF',
                  borderColor: isDark ? '#304442' : '#DCE5E1',
                  borderRadius: '8px',
                  fontFamily: 'monospace',
                  fontSize: '11px',
                  color: isDark ? '#E8F1EE' : '#172B28',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'sans-serif' }} />
              <Bar dataKey="pm25" name="PM2.5" fill="#087F72" radius={[3, 3, 0, 0]} />
              <Bar dataKey="pm10" name="PM10" fill="#159DB0" radius={[3, 3, 0, 0]} />
              <Bar dataKey="no2" name="NO₂" fill="#D5A33A" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
