import React from 'react';
import { useAQI } from '../../context/AQIContext';
import { Calendar, TrendingUp } from 'lucide-react';

export const ForecastTimeline: React.FC = () => {
  const { airQuality } = useAQI();

  if (!airQuality || !airQuality.forecast || airQuality.forecast.length === 0) return null;

  // Show next 24 hourly forecast items
  const next24h = airQuality.forecast.slice(0, 24);

  const getAQIColor = (aqi?: number) => {
    if (!aqi) return '#64748b';
    if (aqi <= 50) return '#10b981';
    if (aqi <= 100) return '#f59e0b';
    if (aqi <= 150) return '#f97316';
    if (aqi <= 200) return '#ef4444';
    if (aqi <= 300) return '#8b5cf6';
    return '#7f1d1d';
  };

  return (
    <div className="card-metric rounded-lg p-5 terminal-border space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Calendar className="w-4 h-4 text-cyanAccent" />
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider font-mono">
            24-Hour Predictive Environmental Forecast
          </h3>
        </div>
        <span className="text-[11px] font-mono text-slate-400">
          Source: CAMS Atmospheric Transport Model
        </span>
      </div>

      <div className="overflow-x-auto pb-2 pt-1">
        <div className="flex space-x-2.5 min-w-max">
          {next24h.map((item, idx) => {
            const timeObj = new Date(item.time);
            const hourLabel = timeObj.toLocaleTimeString([], { hour: 'numeric', hour12: true });
            const aqi = item.us_aqi || Math.round((item.pm25 || 10) * 2.2);
            const color = getAQIColor(aqi);

            return (
              <div
                key={idx}
                className="bg-navy-950/70 border border-slate-800/80 rounded p-2.5 flex flex-col items-center justify-between min-w-[70px] hover:border-slate-700 transition-colors"
              >
                <span className="text-[10px] font-mono text-slate-400">{hourLabel}</span>
                <span
                  className="text-base font-bold font-mono my-1"
                  style={{ color }}
                >
                  {aqi}
                </span>
                <div className="w-full h-1 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${Math.min(100, (aqi / 300) * 100)}%`, backgroundColor: color }}
                  />
                </div>
                <span className="text-[9px] font-mono text-slate-500 mt-1">
                  PM2.5: {item.pm25 !== undefined ? Math.round(item.pm25) : '—'}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
