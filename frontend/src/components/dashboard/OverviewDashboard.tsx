import React from 'react';
import { useAQI } from '../../context/AQIContext';
import { AQIScoreCard } from './AQIScoreCard';
import { PollutantGrid } from './PollutantGrid';
import { ForecastTimeline } from './ForecastTimeline';
import { Radio, RefreshCw, CheckCircle2, ShieldAlert } from 'lucide-react';

export const OverviewDashboard: React.FC = () => {
  const { airQuality, loading, error, activeCity, popularCities, setActiveCity } = useAQI();

  if (loading && !airQuality) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3">
        <RefreshCw className="w-8 h-8 text-cyanAccent animate-spin" />
        <p className="text-sm font-mono text-slate-400">
          Ingesting environmental sensor data for {activeCity.name}...
        </p>
      </div>
    );
  }

  if (error && !airQuality) {
    return (
      <div className="p-6 bg-red-950/40 border border-red-800/60 rounded-lg text-center space-y-2">
        <ShieldAlert className="w-8 h-8 text-red-400 mx-auto" />
        <h3 className="text-base font-semibold text-red-200">Sensor Ingestion Error</h3>
        <p className="text-xs text-red-300 font-mono">{error}</p>
      </div>
    );
  }

  if (!airQuality) return null;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* City Quick-Select Bar */}
      <div className="flex items-center space-x-2 overflow-x-auto pb-1 scrollbar-none">
        <span className="text-[11px] font-mono uppercase tracking-wider text-slate-500 shrink-0">
          Global Terminals:
        </span>
        {popularCities.slice(0, 7).map((city) => (
          <button
            key={city.name}
            onClick={() => setActiveCity(city)}
            className={`px-3 py-1 rounded text-xs font-mono transition-colors shrink-0 ${
              activeCity.name === city.name
                ? 'bg-cyanAccent/15 text-cyanAccent border border-cyanAccent/40 font-semibold'
                : 'bg-navy-900 text-slate-400 hover:text-slate-200 border border-slate-800'
            }`}
          >
            {city.name}
          </button>
        ))}
      </div>

      {/* Data Integrity & Attribution Banner */}
      <div className="bg-navy-900/90 border border-surface-border rounded-lg px-4 py-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center space-x-2">
          {airQuality.is_ground_observation ? (
            <span className="flex items-center text-emerald-400 font-mono font-medium">
              <Radio className="w-3.5 h-3.5 mr-1 animate-pulse" />
              PHYSICAL GROUND STATION ACTIVE
            </span>
          ) : (
            <span className="flex items-center text-cyanAccent font-mono font-medium">
              <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
              ATMOSPHERIC MODEL REANALYSIS (CAMS ENSEMBLE)
            </span>
          )}
          <span className="text-slate-600">|</span>
          <span className="text-slate-300 font-mono truncate max-w-md">
            Source: {airQuality.primary_source}
          </span>
        </div>

        <div className="flex items-center space-x-3 text-[11px] font-mono text-slate-400">
          <span>Freshness: ~{airQuality.data_freshness_minutes}m ago</span>
          <span className="text-emerald-400 bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-800/40">
            VERIFIED
          </span>
        </div>
      </div>

      {/* Main AQI Score & Breakdowns */}
      <AQIScoreCard />

      {/* Monitored Pollutant Matrix */}
      <PollutantGrid />

      {/* 24-Hour Forecast Timeline */}
      <ForecastTimeline />
    </div>
  );
};
