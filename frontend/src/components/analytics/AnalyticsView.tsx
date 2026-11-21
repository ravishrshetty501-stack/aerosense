import React, { useState } from 'react';
import { useAQI } from '../../context/AQIContext';
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
import { LineChart, AlertTriangle, Filter, Calendar } from 'lucide-react';

export const AnalyticsView: React.FC = () => {
  const { airQuality, activeCity } = useAQI();
  const [selectedPollutant, setSelectedPollutant] = useState<'pm25' | 'pm10' | 'no2' | 'o3'>('pm25');

  if (!airQuality) return null;

  // Combine past 48h history and 24h forecast into a contiguous series
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

  const pollutantColors = {
    pm25: '#00f2fe',
    pm10: '#38bdf8',
    no2: '#f59e0b',
    o3: '#ec4899',
  };

  const currentVal = airQuality.measurements[selectedPollutant]?.value || 0;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <LineChart className="w-5 h-5 text-cyanAccent" />
            <h2 className="text-xl font-bold tracking-tight text-white font-mono">
              Pollution Analytics & Spike Detection: {activeCity.name}
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Contiguous 72-hour timeline (48h verified historical reanalysis + 24h atmospheric model forecast).
          </p>
        </div>

        {/* Pollutant Tabs */}
        <div className="flex items-center bg-navy-950 p-1 rounded-md border border-slate-800">
          {(['pm25', 'pm10', 'no2', 'o3'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setSelectedPollutant(p)}
              className={`px-3 py-1.5 text-xs font-mono rounded transition-colors ${
                selectedPollutant === p
                  ? 'bg-navy-800 text-cyanAccent font-semibold border border-slate-700'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {p.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Main Multi-Period Chart */}
      <div className="card-metric rounded-lg p-5 terminal-border space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-xs font-mono uppercase text-slate-400 tracking-wider">
              {selectedPollutant.toUpperCase()} Concentration Trajectory
            </span>
            <div className="text-2xl font-bold font-mono text-slate-100 mt-0.5">
              Current: {currentVal} µg/m³
            </div>
          </div>
          <div className="flex items-center space-x-3 text-xs font-mono text-slate-400">
            <span className="flex items-center">
              <span className="w-3 h-3 rounded-sm bg-cyanAccent mr-1.5 opacity-80" /> Observed History
            </span>
            <span className="flex items-center">
              <span className="w-3 h-3 rounded-sm bg-purple-500 mr-1.5 opacity-80" /> Model Forecast
            </span>
          </div>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={combinedSeries} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="pollutantGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={pollutantColors[selectedPollutant]} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={pollutantColors[selectedPollutant]} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 10, fill: '#64748b' }} />
              <YAxis stroke="#64748b" tick={{ fontSize: 10, fill: '#64748b' }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid rgba(56, 189, 248, 0.2)',
                  borderRadius: '6px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  color: '#f8fafc',
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

      {/* Secondary Multi-Pollutant Stacked Comparison */}
      <div className="card-metric rounded-lg p-5 terminal-border space-y-3">
        <h3 className="text-sm font-semibold font-mono text-slate-200 uppercase tracking-wider">
          Multi-Pollutant Hourly Distribution
        </h3>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={combinedSeries.slice(-18)} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 10, fill: '#64748b' }} />
              <YAxis stroke="#64748b" tick={{ fontSize: 10, fill: '#64748b' }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid rgba(56, 189, 248, 0.2)',
                  borderRadius: '6px',
                  fontFamily: 'monospace',
                  fontSize: '11px',
                }}
              />
              <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace' }} />
              <Bar dataKey="pm25" name="PM2.5" fill="#00f2fe" radius={[2, 2, 0, 0]} />
              <Bar dataKey="pm10" name="PM10" fill="#38bdf8" radius={[2, 2, 0, 0]} />
              <Bar dataKey="no2" name="NO₂" fill="#f59e0b" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
