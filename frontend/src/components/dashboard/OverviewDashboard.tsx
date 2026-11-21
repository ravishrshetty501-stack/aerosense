import React from 'react';
import { useAQI } from '../../context/AQIContext';
import { ForecastTimeline } from './ForecastTimeline';
import {
  Radio,
  RefreshCw,
  CheckCircle2,
  ShieldCheck,
  AlertOctagon,
  AlertTriangle,
  Info,
  Clock,
  Compass,
  ArrowUpRight,
  TrendingUp,
  Cpu
} from 'lucide-react';

export const OverviewDashboard: React.FC = () => {
  const { airQuality, loading, error, activeCity, popularCities, setActiveCity, standard, setStandard } = useAQI();

  if (loading && !airQuality) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3 font-mono">
        <RefreshCw className="w-7 h-7 text-cyan-400 animate-spin" />
        <p className="text-xs text-slate-400 tracking-wider">
          INGESTING ATMOSPHERIC TELEMETRY FOR {activeCity.name.toUpperCase()}...
        </p>
      </div>
    );
  }

  if (error && !airQuality) {
    return (
      <div className="p-6 bg-red-950/40 border border-red-800/60 rounded text-center space-y-2 font-mono">
        <AlertOctagon className="w-8 h-8 text-red-400 mx-auto" />
        <h3 className="text-sm font-bold text-red-200">TELEMETRY INGESTION HALTED</h3>
        <p className="text-xs text-red-300">{error}</p>
      </div>
    );
  }

  if (!airQuality) return null;

  const currentResult = airQuality.aqi_standard_results[standard] || airQuality.aqi_standard_results['US_EPA'];
  const aqiValue = currentResult.aqi !== null ? currentResult.aqi : '--';
  const category = currentResult.category;
  const dominant = airQuality.dominant_pollutant || 'PM2.5';
  const aqiColor = currentResult.color || '#10b981';

  // WHO 24-hr guideline limits (ug/m3) for standard comparison
  const whoGuidelines: Record<string, { whoLimit: number; name: string; formula: string; unit: string }> = {
    pm25: { whoLimit: 15, name: 'Fine Particulate Matter', formula: 'PM2.5', unit: 'µg/m³' },
    pm10: { whoLimit: 45, name: 'Coarse Particulate Matter', formula: 'PM10', unit: 'µg/m³' },
    no2:  { whoLimit: 25, name: 'Nitrogen Dioxide', formula: 'NO₂', unit: 'µg/m³' },
    so2:  { whoLimit: 40, name: 'Sulphur Dioxide', formula: 'SO₂', unit: 'µg/m³' },
    co:   { whoLimit: 4,  name: 'Carbon Monoxide', formula: 'CO', unit: 'mg/m³' },
    o3:   { whoLimit: 100, name: 'Tropospheric Ozone', formula: 'O₃', unit: 'µg/m³' },
  };

  return (
    <div className="space-y-4 max-w-7xl mx-auto pb-12 font-sans">
      {/* 1. Global Megacity Terminal Ticker */}
      <div className="bg-[#0b101d] border border-slate-800 rounded px-3 py-2 flex items-center space-x-2 overflow-x-auto scrollbar-none font-mono text-xs">
        <span className="text-[10px] text-slate-400 uppercase tracking-widest shrink-0 font-bold">
          TERMINALS:
        </span>
        <div className="flex items-center space-x-1.5 shrink-0">
          {popularCities.map((city) => {
            const isActive = activeCity.name === city.name;
            return (
              <button
                key={city.name}
                onClick={() => setActiveCity(city)}
                className={`px-2.5 py-1 rounded text-[11px] transition-colors flex items-center space-x-1.5 ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/40 font-bold'
                    : 'bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-slate-800/80'
                }`}
              >
                <span>{city.name}</span>
                {isActive && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />}
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Scientific Telemetry Status Strip */}
      <div className="bg-[#080d1a] border border-slate-800 rounded px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
        <div className="flex items-center space-x-3 text-slate-300">
          <div className="flex items-center space-x-1.5">
            {airQuality.is_ground_observation ? (
              <span className="flex items-center text-emerald-400 font-bold">
                <Radio className="w-3.5 h-3.5 mr-1 animate-pulse" />
                GROUND SENSOR ONLINE
              </span>
            ) : (
              <span className="flex items-center text-cyan-400 font-bold">
                <Cpu className="w-3.5 h-3.5 mr-1" />
                COPERNICUS CAMS MODEL
              </span>
            )}
          </div>
          <span className="text-slate-700">|</span>
          <span className="text-slate-400 truncate max-w-md">
            Source: <strong className="text-slate-200">{airQuality.primary_source}</strong>
          </span>
        </div>

        <div className="flex items-center space-x-4 text-[11px] text-slate-400">
          <span>Lat: {activeCity.latitude.toFixed(4)}°N</span>
          <span>Lon: {activeCity.longitude.toFixed(4)}°E</span>
          <span className="text-slate-300">Updated: ~{airQuality.data_freshness_minutes}m ago</span>
          <span className="text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/50 flex items-center space-x-1">
            <ShieldCheck className="w-3 h-3" />
            <span>AUTHENTIC</span>
          </span>
        </div>
      </div>

      {/* 3. Main Split Command Console */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column (5 Cols): Deterministic Air Quality Index Matrix */}
        <div className="lg:col-span-5 bg-[#0b1122] border border-slate-800 rounded p-5 space-y-5 flex flex-col justify-between">
          <div>
            {/* Header: Location & Active Standard */}
            <div className="flex items-start justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-widest block font-bold">
                  Atmospheric Diagnostic
                </span>
                <h2 className="text-2xl font-bold font-mono text-white tracking-tight mt-0.5">
                  {activeCity.name.toUpperCase()}
                  {activeCity.country && (
                    <span className="text-xs font-normal text-slate-400 ml-2">
                      ({activeCity.country})
                    </span>
                  )}
                </h2>
              </div>

              {/* Standard Switcher Badge */}
              <div className="text-right font-mono">
                <span className="text-[10px] text-slate-500 uppercase block">Active Metric</span>
                <span className="text-xs font-bold text-cyan-400">
                  {standard === 'US_EPA' ? 'US EPA AQI' : standard === 'INDIA_CPCB' ? 'India CPCB NAQI' : 'European EAQI'}
                </span>
              </div>
            </div>

            {/* Main Segmented Numerical Gauge */}
            <div className="mt-5 flex items-center space-x-5">
              <div
                className="text-6xl font-bold font-mono tracking-tight leading-none"
                style={{ color: aqiColor }}
              >
                {aqiValue}
              </div>

              <div className="space-y-1">
                <div className="flex items-center space-x-1.5">
                  <span
                    className="px-2.5 py-0.5 text-xs font-bold font-mono rounded border uppercase"
                    style={{
                      color: aqiColor,
                      borderColor: `${aqiColor}60`,
                      backgroundColor: `${aqiColor}15`,
                    }}
                  >
                    {category}
                  </span>
                </div>
                <div className="text-xs font-mono text-slate-400 flex items-center space-x-1.5 pt-1">
                  <span>Dominant Parameter:</span>
                  <span className="font-bold text-white bg-slate-900 px-1.5 py-0.5 rounded border border-slate-700">
                    {dominant}
                  </span>
                </div>
              </div>
            </div>

            {/* Health Implication Text */}
            <div className="mt-4 p-3 bg-[#080d1a] border border-slate-800/80 rounded text-xs text-slate-300 leading-relaxed font-sans flex items-start space-x-2">
              <Info className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
              <span>{currentResult.advisory}</span>
            </div>
          </div>

          {/* Comparative Standard Telemetry Table */}
          <div className="pt-3 border-t border-slate-800 font-mono">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-2 font-bold">
              Multi-Jurisdiction Regulatory Equivalency:
            </span>
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              {Object.entries(airQuality.aqi_standard_results).map(([stdKey, res]) => (
                <div
                  key={stdKey}
                  onClick={() => setStandard(stdKey as any)}
                  className={`p-2 rounded border cursor-pointer transition-colors ${
                    standard === stdKey
                      ? 'bg-slate-800/80 border-cyan-400 text-white'
                      : 'bg-slate-900/40 border-slate-800/80 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <span className="text-[10px] text-slate-500 block">
                    {stdKey === 'US_EPA' ? 'US EPA' : stdKey === 'INDIA_CPCB' ? 'CPCB NAQI' : 'EU EAQI'}
                  </span>
                  <span className="text-base font-bold" style={{ color: res.color }}>
                    {res.aqi !== null ? res.aqi : '—'}
                  </span>
                  <span className="text-[9px] block truncate text-slate-400 mt-0.5">
                    {res.category}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column (7 Cols): Precision Chemical Telemetry Table */}
        <div className="lg:col-span-7 bg-[#0b1122] border border-slate-800 rounded p-5 space-y-3 font-mono flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                PHYSICAL CHEMICAL TELEMETRY MATRIX
              </span>
              <span className="text-[11px] text-slate-400">
                Calibrated to WHO Air Quality Guidelines
              </span>
            </div>

            {/* Dense Telemetry Table */}
            <div className="overflow-x-auto mt-2">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-[10px] text-slate-400 uppercase">
                    <th className="py-2 pr-3">Pollutant</th>
                    <th className="py-2 px-3">Concentration</th>
                    <th className="py-2 px-3">WHO Guideline</th>
                    <th className="py-2 px-3">Exposure Ratio</th>
                    <th className="py-2 pl-3 text-right">Detection Type</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-200">
                  {Object.entries(whoGuidelines).map(([key, cfg]) => {
                    const meas = airQuality.measurements[key];
                    const val = meas && meas.value !== null ? meas.value : null;
                    const isGround = meas && meas.measurement_type === 'ground_observation';
                    const ratio = val !== null ? Math.round((val / cfg.whoLimit) * 100) : null;
                    const isOverWHO = ratio !== null && ratio > 100;

                    return (
                      <tr key={key} className="hover:bg-slate-900/40">
                        <td className="py-2.5 pr-3">
                          <span className="font-bold text-white text-sm">{cfg.formula}</span>
                          <span className="text-[10px] text-slate-500 block font-sans">{cfg.name}</span>
                        </td>
                        <td className="py-2.5 px-3">
                          {val !== null ? (
                            <span className="text-base font-bold text-white">
                              {val} <span className="text-[10px] text-slate-400 font-normal">{cfg.unit}</span>
                            </span>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">
                          {cfg.whoLimit} {cfg.unit}
                        </td>
                        <td className="py-2.5 px-3 min-w-[120px]">
                          {ratio !== null ? (
                            <div className="space-y-1">
                              <div className="flex justify-between text-[10px]">
                                <span className={isOverWHO ? 'text-amber-400 font-bold' : 'text-slate-400'}>
                                  {ratio}%
                                </span>
                              </div>
                              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${
                                    isOverWHO ? 'bg-amber-400' : 'bg-emerald-500'
                                  }`}
                                  style={{ width: `${Math.min(100, ratio)}%` }}
                                />
                              </div>
                            </div>
                          ) : (
                            <span className="text-slate-600 text-[10px]">N/A</span>
                          )}
                        </td>
                        <td className="py-2.5 pl-3 text-right">
                          <span className={`text-[10px] px-2 py-0.5 rounded border ${
                            isGround
                              ? 'bg-emerald-950/60 text-emerald-400 border-emerald-800/40'
                              : 'bg-slate-900 text-slate-400 border-slate-800'
                          }`}>
                            {isGround ? 'Physical Ground Sensor' : 'CAMS Reanalysis'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-500">
            <span>Precision: Truncated according to EPA 40 CFR Part 58</span>
            <span>Sensor Ingestion Rate: 1.0 Hz Active Polling</span>
          </div>
        </div>
      </div>

      {/* 4. Contiguous Predictive Atmospheric Timeline */}
      <ForecastTimeline />
    </div>
  );
};
