import React from 'react';
import { useAQI } from '../../context/AQIContext';
import { ShieldCheck, AlertTriangle, AlertOctagon, Info, Flame } from 'lucide-react';

export const AQIScoreCard: React.FC = () => {
  const { airQuality, standard, activeCity } = useAQI();

  if (!airQuality) return null;

  const currentResult = airQuality.aqi_standard_results[standard] || airQuality.aqi_standard_results['US_EPA'];
  const aqiValue = currentResult.aqi !== null ? currentResult.aqi : '--';
  const category = currentResult.category;
  const dominant = airQuality.dominant_pollutant || 'PM2.5';
  const color = currentResult.color || '#10b981';

  const getCategoryIcon = () => {
    if (typeof aqiValue === 'number') {
      if (aqiValue > 200) return <AlertOctagon className="w-5 h-5 text-red-500" />;
      if (aqiValue > 100) return <AlertTriangle className="w-5 h-5 text-amber-500" />;
    }
    return <ShieldCheck className="w-5 h-5 text-emerald-400" />;
  };

  return (
    <div className="card-metric rounded-lg p-5 terminal-border relative overflow-hidden">
      {/* Background Subtle Gradient Glow */}
      <div
        className="absolute -top-12 -right-12 w-48 h-48 rounded-full blur-3xl opacity-15 pointer-events-none"
        style={{ backgroundColor: color }}
      />

      {/* Top Header: City & Coordinates */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              {activeCity.name}
            </h2>
            {activeCity.country && (
              <span className="px-2 py-0.5 text-[11px] font-mono bg-navy-800 text-slate-300 rounded border border-slate-700">
                {activeCity.country}
              </span>
            )}
          </div>
          <p className="text-xs font-mono text-slate-400 mt-0.5">
            Coordinates: {activeCity.latitude.toFixed(4)}°N, {activeCity.longitude.toFixed(4)}°E
          </p>
        </div>

        {/* Standard Badge */}
        <div className="text-right">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Standard</span>
          <span className="text-xs font-mono font-semibold text-cyanAccent">
            {standard === 'US_EPA' ? 'US EPA' : standard === 'INDIA_CPCB' ? 'India CPCB' : 'EU EAQI'}
          </span>
        </div>
      </div>

      {/* Main AQI Display */}
      <div className="mt-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-baseline space-x-4">
          <div
            className="text-5xl sm:text-6xl font-bold font-mono tracking-tight"
            style={{ color }}
          >
            {aqiValue}
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              {getCategoryIcon()}
              <span className="text-base sm:text-lg font-semibold text-slate-100">
                {category}
              </span>
            </div>
            <div className="text-xs text-slate-400 mt-0.5 flex items-center space-x-2">
              <span>Dominant Pollutant:</span>
              <span className="px-1.5 py-0.5 bg-navy-800 border border-slate-700 text-cyanAccent font-mono rounded font-medium">
                {dominant}
              </span>
            </div>
          </div>
        </div>

        {/* Secondary Standards Comparison Preview */}
        <div className="bg-navy-950/80 p-3 rounded-md border border-slate-800/80 flex sm:flex-col gap-2 min-w-[160px]">
          <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 block">
            Standard Breakdown
          </span>
          {Object.entries(airQuality.aqi_standard_results).map(([stdKey, res]) => (
            <div key={stdKey} className="flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400">{stdKey === 'US_EPA' ? 'US EPA' : stdKey === 'INDIA_CPCB' ? 'CPCB' : 'EAQI'}:</span>
              <span className="font-semibold" style={{ color: res.color }}>
                {res.aqi !== null ? res.aqi : 'N/A'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Health Advisory Text */}
      <div className="mt-5 pt-4 border-t border-slate-800/80 flex items-start space-x-2.5">
        <Info className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
        <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
          {currentResult.advisory}
        </p>
      </div>
    </div>
  );
};
