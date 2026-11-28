import React from 'react';
import { useAQI } from '../../context/AQIContext';
import { Activity, Radio, Cpu } from 'lucide-react';

export const PollutantGrid: React.FC = () => {
  const { airQuality } = useAQI();

  if (!airQuality || !airQuality.measurements) return null;

  const pollutantConfigs: Record<string, { label: string; formula: string; description: string }> = {
    pm25: { label: 'Fine Particulate Matter', formula: 'PM2.5', description: 'Particles ≤ 2.5 µm that penetrate deep into lung tissue' },
    pm10: { label: 'Coarse Particulate Matter', formula: 'PM10', description: 'Inhalable dust, pollen and mold particles ≤ 10 µm' },
    no2:  { label: 'Nitrogen Dioxide', formula: 'NO₂', description: 'Combustion gas from vehicular exhaust and power plants' },
    so2:  { label: 'Sulphur Dioxide', formula: 'SO₂', description: 'Industrial gas emitted by fossil fuel combustion and refineries' },
    co:   { label: 'Carbon Monoxide', formula: 'CO', description: 'Colorless toxic gas from incomplete hydrocarbon combustion' },
    o3:   { label: 'Ground-Level Ozone', formula: 'O₃', description: 'Secondary pollutant formed by sunlight and chemical precursors' },
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider font-mono">
          Monitored Environmental Parameters
        </h3>
        <span className="text-xs text-slate-400 font-mono">
          {Object.values(airQuality.measurements).filter((m) => Boolean(m) && typeof m.value === 'number' && Number.isFinite(m.value)).length} Active Sensors
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
        {Object.entries(pollutantConfigs).map(([key, cfg]) => {
          const meas = airQuality.measurements[key];
          const hasValue = Boolean(meas) && typeof meas.value === 'number' && Number.isFinite(meas.value);
          const displayValue = hasValue ? (Object.is(meas.value, -0) ? 0 : meas.value) : '—';
          const isGround = hasValue && meas.measurement_type === 'ground_observation';

          return (
            <div
              key={key}
              className="bg-navy-900/95 rounded-lg p-4 border border-slate-800/80 hover:border-slate-700 transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="text-base font-bold font-mono text-cyanAccent">
                  {cfg.formula}
                </span>
                {hasValue ? (
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded flex items-center space-x-1 ${
                    isGround 
                      ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50' 
                      : 'bg-navy-950 text-slate-400 border border-slate-800'
                  }`}>
                    {isGround ? <Radio className="w-2.5 h-2.5 mr-1" /> : <Cpu className="w-2.5 h-2.5 mr-1" />}
                    <span>{isGround ? 'Ground Sensor' : 'Model Estimate'}</span>
                  </span>
                ) : (
                  <span className="text-[10px] font-mono px-2 py-0.5 bg-navy-950 text-slate-500 rounded border border-slate-800">
                    Not Monitored
                  </span>
                )}
              </div>

              <div className="mt-3 flex items-baseline space-x-2">
                <span className="text-2xl sm:text-3xl font-bold font-mono text-slate-100">
                  {displayValue}
                </span>
                <span className="text-xs font-mono text-slate-400">
                  {hasValue ? meas.unit || '' : ''}
                </span>
              </div>

              <p className="text-xs text-slate-400 mt-2 line-clamp-2">
                {cfg.description}
              </p>

              {hasValue && (
                <div className="mt-3 pt-2.5 border-t border-slate-800/60 flex items-center justify-between text-[10px] font-mono text-slate-500">
                  <span className="truncate max-w-[150px]">{meas.source}</span>
                  <span>{new Date(meas.observation_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
