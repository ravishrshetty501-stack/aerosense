import React from 'react';
import { useAQI } from '../../context/AQIContext';
import { Calendar, TrendingUp } from 'lucide-react';

export const ForecastTimeline: React.FC = () => {
  const { airQuality } = useAQI();

  if (!airQuality || !airQuality.forecast || airQuality.forecast.length === 0) return null;

  // Show next 24 hourly forecast points
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
    <div className="bg-[#0b1122] border border-slate-800 rounded p-4 font-mono space-y-3">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center space-x-2">
          <Calendar className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
            24-HOUR HIGH-RESOLUTION PREDICTIVE ATMOSPHERIC TIMELINE
          </span>
        </div>
        <span className="text-[10px] text-slate-400">
          Atmospheric Transport Dispersion: ECMWF CAMS Ensemble
        </span>
      </div>

      <div className="overflow-x-auto pb-1 pt-1">
        <div className="flex space-x-1.5 min-w-max">
          {next24h.map((item, idx) => {
            const timeObj = new Date(item.time);
            const hourLabel = timeObj.toLocaleTimeString([], { hour: 'numeric', hour12: true });
            const aqi = item.us_aqi || Math.round((item.pm25 || 10) * 2.2);
            const color = getAQIColor(aqi);

            return (
              <div
                key={idx}
                className="bg-[#080d1a] border border-slate-800/80 rounded p-2 flex flex-col items-center justify-between min-w-[64px] hover:border-slate-700 transition-colors"
              >
                <span className="text-[9px] text-slate-400">{hourLabel}</span>
                <span
                  className="text-sm font-bold my-1"
                  style={{ color }}
                >
                  {aqi}
                </span>
                <div className="w-full h-1 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${Math.min(100, (aqi / 300) * 100)}%`, backgroundColor: color }}
                  />
                </div>
                <span className="text-[8px] text-slate-400 mt-1">
                  {item.pm25 !== undefined ? `${Math.round(item.pm25)} µg` : '—'}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
