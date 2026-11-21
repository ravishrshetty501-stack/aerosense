import React from 'react';
import { useAQI } from '../../context/AQIContext';
import { Calendar } from 'lucide-react';

export const ForecastTimeline: React.FC = () => {
  const { airQuality } = useAQI();

  if (!airQuality || !airQuality.forecast || airQuality.forecast.length === 0) return null;

  // Show next 24 hourly forecast points
  const next24h = airQuality.forecast.slice(0, 24);

  const getAQIColor = (aqi?: number) => {
    if (!aqi) return '#647570';
    if (aqi <= 50) return '#23966B';
    if (aqi <= 100) return '#D5A33A';
    if (aqi <= 150) return '#E27C42';
    if (aqi <= 200) return '#C94E55';
    if (aqi <= 300) return '#8E44AD';
    return '#5B2C6F';
  };

  return (
    <div className="bg-clima-surface dark:bg-darkClima-surface border border-clima-border dark:border-darkClima-border rounded-xl p-5 shadow-floating dark:shadow-floating-dark space-y-3 font-sans">
      <div className="flex items-center justify-between border-b border-clima-border dark:border-darkClima-border pb-2.5">
        <div className="flex items-center space-x-2">
          <Calendar className="w-4 h-4 text-clima-accent dark:text-darkClima-accent" />
          <span className="text-xs font-bold text-clima-text dark:text-darkClima-text uppercase tracking-wider">
            24-Hour High-Resolution Predictive Atmospheric Timeline
          </span>
        </div>
        <span className="text-[10px] font-mono text-clima-muted dark:text-darkClima-muted">
          ECMWF Copernicus CAMS Ensemble
        </span>
      </div>

      <div className="overflow-x-auto pb-1 pt-1">
        <div className="flex space-x-2 min-w-max">
          {next24h.map((item, idx) => {
            const timeObj = new Date(item.time);
            const hourLabel = timeObj.toLocaleTimeString([], { hour: 'numeric', hour12: true });
            const aqi = item.us_aqi || Math.round((item.pm25 || 10) * 2.2);
            const color = getAQIColor(aqi);

            return (
              <div
                key={idx}
                className="bg-clima-subtle/80 dark:bg-darkClima-subtle/80 border border-clima-border dark:border-darkClima-border rounded-lg p-2.5 flex flex-col items-center justify-between min-w-[68px] hover:border-clima-accent dark:hover:border-darkClima-accent transition-colors"
              >
                <span className="text-[10px] text-clima-muted dark:text-darkClima-muted font-sans font-medium">{hourLabel}</span>
                <span
                  className="text-sm font-bold font-mono my-1"
                  style={{ color }}
                >
                  {aqi}
                </span>
                <div className="w-full h-1.5 bg-clima-border dark:bg-darkClima-border rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${Math.min(100, (aqi / 250) * 100)}%`, backgroundColor: color }}
                  />
                </div>
                <span className="text-[9px] text-clima-muted dark:text-darkClima-muted font-mono mt-1">
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
