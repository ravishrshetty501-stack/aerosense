import React from 'react';
import { useAQI } from '../../context/AQIContext';
import { AQIStandard, AQIStandardResult, AirQualityResponse } from '../../types/airQuality';
import { ForecastTimeline } from './ForecastTimeline';
import {
  WHO_GUIDELINES,
  calculatePollutantExposureRatio,
  getAqiScaleColor,
} from '../../utils/airQualityHelpers';
import {
  Radio,
  RefreshCw,
  ShieldAlert,
  Info,
  MapPin,
  Cpu,
  Sparkles,
  ArrowRight,
  Globe,
  BellRing
} from 'lucide-react';

function isFiniteNumber(val: unknown): val is number {
  return typeof val === 'number' && Number.isFinite(val);
}

function normalizeFiniteNumber(val: number): number {
  return Object.is(val, -0) ? 0 : val;
}

export interface ResolvedStandardBreakdownDisplay {
  hasFiniteAqi: boolean;
  aqiDisplay: number | string;
  color: string;
  category: string;
}

export interface ResolvedStandardAqiDisplay extends ResolvedStandardBreakdownDisplay {
  dominantPollutant: string;
  advisory: string;
}

/**
 * Resolves display metadata for an individual AQI regulatory standard entry
 * while rejecting null/undefined/NaN/Infinity and preserving genuine 0 AQI.
 */
export function resolveStandardBreakdownDisplay(
  result: AQIStandardResult | undefined,
  unavailableText: string = '—'
): ResolvedStandardBreakdownDisplay {
  const rawAqi = result?.aqi;
  const hasFiniteAqi = isFiniteNumber(rawAqi);
  const aqiDisplay = hasFiniteAqi ? normalizeFiniteNumber(rawAqi) : unavailableText;
  const color = hasFiniteAqi
    ? result?.color || getAqiScaleColor(rawAqi)
    : '#647570';
  const category = result?.category?.trim() ? result.category : 'Unavailable';

  return { hasFiniteAqi, aqiDisplay, color, category };
}

/**
 * Resolves primary AQI score-card and dashboard summary metrics without fabricating
 * default pollutants or healthy-green styling when AQI data is missing.
 */
export function resolveStandardAqiDisplay(
  airQuality: Pick<AirQualityResponse, 'aqi_standard_results' | 'dominant_pollutant'>,
  standard: AQIStandard,
  unavailableText: string = '—'
): ResolvedStandardAqiDisplay {
  const currentResult =
    airQuality.aqi_standard_results?.[standard] || airQuality.aqi_standard_results?.['US_EPA'];
  const base = resolveStandardBreakdownDisplay(currentResult, unavailableText);
  const stdDominant = currentResult?.dominant_pollutant?.trim();
  const topDominant = airQuality.dominant_pollutant?.trim();
  const dominantPollutant = stdDominant
    ? stdDominant
    : base.hasFiniteAqi && topDominant
    ? topDominant
    : 'Unavailable';
  const advisory = currentResult?.advisory?.trim()
    ? currentResult.advisory
    : 'Air quality health advisory is currently unavailable.';

  return {
    ...base,
    dominantPollutant,
    advisory,
  };
}

/**
 * Resolves verified telemetry observation mode from actual finite pollutant measurements.
 */
export function resolveObservationSourceStatus(
  airQuality: Pick<AirQualityResponse, 'measurements' | 'is_ground_observation' | 'primary_source'>
): {
  mode: 'ground' | 'model' | 'unavailable';
  primarySource: string;
} {
  const validMeasurements = Object.values(airQuality.measurements || {}).filter(
    (m) => Boolean(m) && isFiniteNumber(m.value)
  );
  const hasGround = validMeasurements.some((m) => m.measurement_type === 'ground_observation');
  const hasModel = validMeasurements.some(
    (m) => m.measurement_type !== 'ground_observation' && m.measurement_type !== 'unavailable'
  );

  let mode: 'ground' | 'model' | 'unavailable' = 'unavailable';
  if (hasGround || (validMeasurements.length > 0 && airQuality.is_ground_observation)) {
    mode = 'ground';
  } else if (hasModel) {
    mode = 'model';
  }

  return {
    mode,
    primarySource: airQuality.primary_source?.trim() ? airQuality.primary_source : 'Unavailable',
  };
}

interface OverviewDashboardProps {
  onNavigateToMap?: () => void;
  onNavigateToAlerts?: () => void;
}

export const OverviewDashboard: React.FC<OverviewDashboardProps> = ({
  onNavigateToMap,
  onNavigateToAlerts,
}) => {
  const { airQuality, loading, error, activeCity, popularCities, setActiveCity, standard, setStandard } = useAQI();

  if (loading && !airQuality) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3 font-sans">
        <RefreshCw className="w-8 h-8 text-atlas-accent dark:text-darkAtlas-accent animate-spin" />
        <p className="text-xs text-atlas-muted dark:text-darkAtlas-muted tracking-wider">
          Ingesting atmospheric measurements for {activeCity.name}...
        </p>
      </div>
    );
  }

  if (error && !airQuality) {
    return (
      <div className="p-6 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/60 rounded-xl text-center space-y-2 font-sans">
        <ShieldAlert className="w-8 h-8 text-red-500 mx-auto" />
        <h3 className="text-sm font-bold text-red-800 dark:text-red-200">Atmospheric Data Unavailable</h3>
        <p className="text-xs text-red-600 dark:text-red-300">{error}</p>
      </div>
    );
  }

  if (!airQuality) return null;

  const {
    hasFiniteAqi,
    aqiDisplay: aqiValue,
    category,
    dominantPollutant: dominant,
    color: aqiColor,
    advisory: currentAdvisory,
  } = resolveStandardAqiDisplay(airQuality, standard);
  const observationStatus = resolveObservationSourceStatus(airQuality);

  // WHO 24-hr guideline reference benchmarks from shared intelligence module
  const whoGuidelines = WHO_GUIDELINES;

  return (
    <div className="space-y-5 max-w-7xl mx-auto pb-12 font-sans">
      {error && (
        <div
          role="alert"
          className="p-3.5 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/60 rounded-xl flex items-center space-x-2.5 text-xs text-red-700 dark:text-red-300"
        >
          <ShieldAlert className="w-4 h-4 text-red-500 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {/* 1. Global Metropolises Quick Filter Strip */}
      <div className="bg-atlas-surface dark:bg-darkAtlas-surface border border-atlas-border dark:border-darkAtlas-border rounded-xl px-4 py-2.5 flex items-center space-x-2 overflow-x-auto scrollbar-none shadow-subtle">
        <span className="text-[11px] text-atlas-muted dark:text-darkAtlas-muted font-semibold uppercase tracking-wider shrink-0 mr-1 flex items-center">
          <MapPin className="w-3.5 h-3.5 text-atlas-accent dark:text-darkAtlas-accent mr-1" /> Terminals:
        </span>
        <div className="flex items-center space-x-2 shrink-0">
          {popularCities.map((city) => {
            const isActive = activeCity.name === city.name;
            return (
              <button
                key={city.name}
                onClick={() => setActiveCity(city)}
                className={`px-3 py-1 rounded-lg text-xs transition-colors flex items-center space-x-1.5 font-medium ${
                  isActive
                    ? 'bg-atlas-accent dark:bg-darkAtlas-accent text-white dark:text-darkAtlas-bg shadow-sm'
                    : 'bg-atlas-subtle dark:bg-darkAtlas-subtle text-atlas-muted dark:text-darkAtlas-muted hover:text-atlas-text dark:hover:text-darkAtlas-text border border-atlas-border dark:border-darkAtlas-border'
                }`}
              >
                <span>{city.name}</span>
                {isActive && <span className="w-1.5 h-1.5 rounded-full bg-white dark:bg-darkAtlas-bg" />}
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Section A: Location Context Header */}
      <div className="bg-atlas-subtle/80 dark:bg-darkAtlas-subtle/80 border border-atlas-border dark:border-darkAtlas-border rounded-xl px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center space-x-3 text-atlas-text dark:text-darkAtlas-text">
          <div className="flex items-center space-x-1.5">
            {observationStatus.mode === 'ground' ? (
              <span className="flex items-center text-atlas-success dark:text-darkAtlas-success font-semibold font-mono text-[11px]">
                <Radio className="w-3.5 h-3.5 mr-1" />
                Physical Ground Observation
              </span>
            ) : observationStatus.mode === 'model' ? (
              <span className="flex items-center text-atlas-secondary dark:text-darkAtlas-secondary font-semibold font-mono text-[11px]">
                <Cpu className="w-3.5 h-3.5 mr-1" />
                Modelled Atmospheric Estimate
              </span>
            ) : (
              <span className="flex items-center text-atlas-muted dark:text-darkAtlas-muted font-semibold font-mono text-[11px]">
                <Info className="w-3.5 h-3.5 mr-1" />
                Observations Unavailable
              </span>
            )}
          </div>
          <span className="text-atlas-border dark:text-darkAtlas-border">|</span>
          <span className="text-atlas-muted dark:text-darkAtlas-muted truncate max-w-md font-sans">
            Source: <strong className="text-atlas-text dark:text-darkAtlas-text">{observationStatus.primarySource}</strong>
          </span>
        </div>

        <div className="flex items-center space-x-4 text-[11px] text-atlas-muted dark:text-darkAtlas-muted font-mono">
          <span>{activeCity.latitude.toFixed(4)}°N, {activeCity.longitude.toFixed(4)}°E</span>
          <span className="text-atlas-text dark:text-darkAtlas-text">
            {isFiniteNumber(airQuality.data_freshness_minutes)
              ? `Updated ~${normalizeFiniteNumber(airQuality.data_freshness_minutes)}m ago`
              : 'Timestamp unavailable'}
          </span>
        </div>
      </div>

      {/* 3. Section B & C: Main Analytical Split Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5" role="region" aria-label="Air Quality Analytical Workspace" aria-live="polite">
        {/* Left Column (5 Cols): AQI Diagnostic Section & Multi-Standard Equivalency */}
        <div className="lg:col-span-5 bg-atlas-surface dark:bg-darkAtlas-surface border border-atlas-border dark:border-darkAtlas-border rounded-xl p-6 space-y-6 flex flex-col justify-between shadow-floating dark:shadow-floating-dark">
          <div>
            {/* Header: Location & Standard */}
            <div className="flex items-start justify-between border-b border-atlas-border dark:border-darkAtlas-border pb-4">
              <div>
                <span className="text-[10px] text-atlas-accent dark:text-darkAtlas-accent uppercase tracking-widest block font-mono font-semibold">
                  Air Quality Diagnostic
                </span>
                <h2 className="text-2xl font-bold text-atlas-text dark:text-darkAtlas-text tracking-tight mt-0.5 font-sans">
                  {activeCity.name}
                  {activeCity.country && (
                    <span className="text-xs font-normal text-atlas-muted dark:text-darkAtlas-muted ml-2">
                      ({activeCity.country})
                    </span>
                  )}
                </h2>
              </div>

              <div className="text-right">
                <span className="text-[10px] text-atlas-muted dark:text-darkAtlas-muted uppercase block font-sans">Active Standard</span>
                <span className="text-xs font-bold text-atlas-accent dark:text-darkAtlas-accent font-mono">
                  {standard === 'US_EPA' ? 'US EPA' : standard === 'INDIA_CPCB' ? 'CPCB NAQI' : 'EU EAQI'}
                </span>
              </div>
            </div>

            {/* Numerical AQI Indicator */}
            <div className="mt-5 flex items-center space-x-6">
              <div
                className="text-6xl font-extrabold font-mono tracking-tight leading-none"
                style={{ color: aqiColor }}
              >
                {aqiValue}
              </div>

              <div className="space-y-1.5">
                <span
                  className="px-3 py-1 text-xs font-bold font-sans rounded-full border uppercase"
                  style={{
                    color: aqiColor,
                    borderColor: `${aqiColor}60`,
                    backgroundColor: `${aqiColor}15`,
                  }}
                >
                  {category}
                </span>
                <div className="text-xs text-atlas-muted dark:text-darkAtlas-muted flex items-center space-x-1.5 pt-1 font-sans">
                  <span>Dominant Pollutant:</span>
                  <span className="font-bold text-atlas-text dark:text-darkAtlas-text bg-atlas-subtle dark:bg-darkAtlas-subtle px-2 py-0.5 rounded border border-atlas-border dark:border-darkAtlas-border font-mono">
                    {dominant}
                  </span>
                </div>
              </div>
            </div>

            {/* Health Advisory Summary */}
            <div className="mt-5 p-4 bg-atlas-subtle dark:bg-darkAtlas-subtle border border-atlas-border dark:border-darkAtlas-border rounded-xl text-xs text-atlas-text dark:text-darkAtlas-text leading-relaxed font-sans flex items-start space-x-2.5">
              <Info className="w-4 h-4 text-atlas-accent dark:text-darkAtlas-accent shrink-0 mt-0.5" />
              <span>{currentAdvisory}</span>
            </div>
          </div>

          {/* Multi-Standard Cross-Reference Table */}
          <div className="pt-4 border-t border-atlas-border dark:border-darkAtlas-border">
            <span className="text-[10px] text-atlas-muted dark:text-darkAtlas-muted uppercase tracking-wider block mb-2.5 font-sans font-semibold">
              Regulatory Standards Cross-Reference:
            </span>
            <div className="grid grid-cols-3 gap-2.5 text-center text-xs">
              {Object.entries(airQuality.aqi_standard_results || {}).map(([stdKey, res]) => {
                const breakdown = resolveStandardBreakdownDisplay(res);
                return (
                  <div
                    key={stdKey}
                    onClick={() => setStandard(stdKey as AQIStandard)}
                    className={`p-2.5 rounded-lg border cursor-pointer transition-all ${
                      standard === stdKey
                        ? 'bg-atlas-subtle dark:bg-darkAtlas-subtle border-atlas-accent dark:border-darkAtlas-accent text-atlas-text dark:text-darkAtlas-text shadow-sm'
                        : 'bg-atlas-surface dark:bg-darkAtlas-surface border-atlas-border dark:border-darkAtlas-border text-atlas-muted dark:text-darkAtlas-muted hover:border-atlas-accent'
                    }`}
                  >
                    <span className="text-[10px] text-atlas-muted dark:text-darkAtlas-muted block font-sans">
                      {stdKey === 'US_EPA' ? 'US EPA' : stdKey === 'INDIA_CPCB' ? 'CPCB' : 'EAQI'}
                    </span>
                    <span className="text-lg font-bold font-mono mt-0.5 block" style={{ color: breakdown.color }}>
                      {breakdown.aqiDisplay}
                    </span>
                    <span className="text-[10px] block truncate text-atlas-muted dark:text-darkAtlas-muted mt-0.5 font-sans">
                      {breakdown.category}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column (7 Cols): Section C Pollutant Matrix */}
        <div className="lg:col-span-7 bg-atlas-surface dark:bg-darkAtlas-surface border border-atlas-border dark:border-darkAtlas-border rounded-xl p-6 space-y-4 flex flex-col justify-between shadow-floating dark:shadow-floating-dark">
          <div>
            <div className="flex items-center justify-between border-b border-atlas-border dark:border-darkAtlas-border pb-3">
              <span className="text-xs font-bold text-atlas-text dark:text-darkAtlas-text uppercase tracking-wider font-sans">
                Monitored Pollutant Concentration Matrix
              </span>
              <span className="text-[11px] text-atlas-muted dark:text-darkAtlas-muted font-sans">
                Benchmark: WHO Air Quality Guidelines
              </span>
            </div>

            {/* Dense Telemetry Table */}
            <div className="overflow-x-auto mt-3">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-atlas-border dark:border-darkAtlas-border text-[10px] text-atlas-muted dark:text-darkAtlas-muted uppercase font-mono">
                    <th className="py-2.5 pr-3">Pollutant</th>
                    <th className="py-2.5 px-3">Concentration</th>
                    <th className="py-2.5 px-3">WHO Guideline</th>
                    <th className="py-2.5 px-3">Exposure Ratio</th>
                    <th className="py-2.5 pl-3 text-right">Detection Type</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-atlas-border/60 dark:divide-darkAtlas-border/60 text-atlas-text dark:text-darkAtlas-text font-sans">
                  {Object.entries(whoGuidelines).map(([key, cfg]) => {
                    const meas = airQuality.measurements?.[key];
                    const val = meas && isFiniteNumber(meas.value) ? normalizeFiniteNumber(meas.value) : null;
                    const isGround = val !== null && meas.measurement_type === 'ground_observation';
                    const ratioVal = val !== null ? calculatePollutantExposureRatio(key, val) : null;
                    const ratio = ratioVal !== null && Number.isFinite(ratioVal) ? Math.round(ratioVal * 100) : null;
                    const isOverWHO = ratio !== null && ratio > 100;

                    return (
                      <tr key={key} className="hover:bg-atlas-subtle/50 dark:hover:bg-darkAtlas-subtle/50 transition-colors">
                        <td className="py-2.5 pr-3">
                          <span className="font-bold text-atlas-text dark:text-darkAtlas-text text-sm font-mono">{cfg.formula}</span>
                          <span className="text-[10px] text-atlas-muted dark:text-darkAtlas-muted block font-sans">{cfg.name}</span>
                        </td>
                        <td className="py-2.5 px-3">
                          {val !== null ? (
                            <span className="text-base font-bold font-mono">
                              {val} <span className="text-[10px] text-atlas-muted dark:text-darkAtlas-muted font-normal">{cfg.unit}</span>
                            </span>
                          ) : (
                            <span className="text-atlas-muted dark:text-darkAtlas-muted font-mono">Unavailable</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-atlas-muted dark:text-darkAtlas-muted font-mono">
                          {cfg.whoLimit} {cfg.unit} <span className="text-[9px] text-atlas-muted dark:text-darkAtlas-muted">({cfg.period})</span>
                        </td>
                        <td className="py-2.5 px-3 min-w-[120px]">
                          {ratio !== null ? (
                            <div className="space-y-1">
                              <div className="flex justify-between text-[10px] font-mono">
                                <span className={isOverWHO ? 'text-atlas-warning dark:text-darkAtlas-warning font-bold' : 'text-atlas-muted dark:text-darkAtlas-muted'}>
                                  {ratio}%
                                </span>
                              </div>
                              <div className="w-full h-1.5 bg-atlas-subtle dark:bg-darkAtlas-subtle rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${
                                    isOverWHO ? 'bg-atlas-warning dark:bg-darkAtlas-warning' : 'bg-atlas-success dark:bg-darkAtlas-success'
                                  }`}
                                  style={{ width: `${Math.min(100, Math.max(0, ratio))}%` }}
                                />
                              </div>
                            </div>
                          ) : (
                            <span className="text-atlas-muted dark:text-darkAtlas-muted text-[10px] font-mono">N/A</span>
                          )}
                        </td>
                        <td className="py-2.5 pl-3 text-right">
                          <span className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                            val === null
                              ? 'bg-atlas-subtle dark:bg-darkAtlas-subtle text-atlas-muted dark:text-darkAtlas-muted'
                              : isGround
                              ? 'bg-atlas-success/15 text-atlas-success dark:text-darkAtlas-success border border-atlas-success/30'
                              : 'bg-atlas-subtle dark:bg-darkAtlas-subtle text-atlas-muted dark:text-darkAtlas-muted'
                          }`}>
                            {val === null ? 'Unavailable' : isGround ? 'Ground Sensor' : 'Model Estimate'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="pt-2 border-t border-atlas-border dark:border-darkAtlas-border flex items-center justify-between text-[10px] text-atlas-muted dark:text-darkAtlas-muted font-mono">
            <span>Breakpoint Rules: EPA 40 CFR Part 58 / CPCB NAQI / EEA EAQI</span>
            <span>Ground Station Sync: Live Active Polling</span>
          </div>
        </div>
      </div>

      {/* 4. Section D & F & G: Map Preview, AI Summary & Recent Alerts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Section D: Map Preview Panel (4 Cols) */}
        <div className="lg:col-span-4 bg-atlas-surface dark:bg-darkAtlas-surface border border-atlas-border dark:border-darkAtlas-border rounded-xl p-5 shadow-floating dark:shadow-floating-dark space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-atlas-border dark:border-darkAtlas-border pb-2.5">
              <span className="text-xs font-bold text-atlas-text dark:text-darkAtlas-text uppercase tracking-wider flex items-center">
                <Globe className="w-3.5 h-3.5 mr-1.5 text-atlas-accent dark:text-darkAtlas-accent" />
                Geospatial Preview
              </span>
              <span className="text-[10px] font-mono text-atlas-muted dark:text-darkAtlas-muted">
                {activeCity.name}
              </span>
            </div>

            <div className="mt-3 bg-atlas-subtle dark:bg-darkAtlas-subtle rounded-lg p-3.5 border border-atlas-border dark:border-darkAtlas-border space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-atlas-muted dark:text-darkAtlas-muted">Latitude:</span>
                <span className="font-mono font-semibold">{activeCity.latitude.toFixed(4)}°N</span>
              </div>
              <div className="flex justify-between">
                <span className="text-atlas-muted dark:text-darkAtlas-muted">Longitude:</span>
                <span className="font-mono font-semibold">{activeCity.longitude.toFixed(4)}°E</span>
              </div>
              <div className="flex justify-between">
                <span className="text-atlas-muted dark:text-darkAtlas-muted">Sensor Coverage:</span>
                <span
                  className={`font-mono font-semibold ${
                    observationStatus.mode === 'ground'
                      ? 'text-atlas-success dark:text-darkAtlas-success'
                      : observationStatus.mode === 'model'
                      ? 'text-atlas-secondary dark:text-darkAtlas-secondary'
                      : 'text-atlas-muted dark:text-darkAtlas-muted'
                  }`}
                >
                  {observationStatus.mode === 'ground'
                    ? 'Active Ground Grid'
                    : observationStatus.mode === 'model'
                    ? 'Modelled Atmospheric Grid'
                    : 'Coverage Unavailable'}
                </span>
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-atlas-border dark:border-darkAtlas-border">
            <button
              onClick={onNavigateToMap}
              className="w-full py-2 bg-atlas-accent dark:bg-darkAtlas-accent hover:opacity-90 text-white dark:text-darkAtlas-bg text-xs font-medium rounded-lg transition-colors flex items-center justify-center space-x-1.5 shadow-sm"
            >
              <span>Explore Interactive Map</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Section F: Environmental Intelligence Summary (5 Cols) */}
        <div className="lg:col-span-5 bg-atlas-surface dark:bg-darkAtlas-surface border border-atlas-border dark:border-darkAtlas-border rounded-xl p-5 shadow-floating dark:shadow-floating-dark space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-atlas-border dark:border-darkAtlas-border pb-2.5">
              <div className="flex items-center space-x-1.5">
                <Sparkles className="w-4 h-4 text-atlas-accent dark:text-darkAtlas-accent" />
                <h3 className="text-xs font-bold text-atlas-text dark:text-darkAtlas-text uppercase tracking-wider">
                  Environmental Intelligence Summary
                </h3>
              </div>
              <span className="text-[10px] font-mono text-atlas-muted dark:text-darkAtlas-muted">
                Gemini Grounded Engine
              </span>
            </div>

            <p className="mt-3 text-xs text-atlas-text dark:text-darkAtlas-text leading-relaxed font-sans">
              {hasFiniteAqi ? (
                <>
                  Ambient air quality in {activeCity.name} is currently categorized as <strong style={{ color: aqiColor }}>{category}</strong> with an index of <strong className="font-mono">{aqiValue}</strong> ({standard.replace('_', ' ')}). The primary contributor to exposure risk is <strong className="font-mono text-atlas-accent dark:text-darkAtlas-accent">{dominant}</strong>. Atmospheric transport dispersion indicates stable boundary layer conditions over the coming hours.
                </>
              ) : (
                <>
                  Real-time AQI telemetry for {activeCity.name} ({standard.replace('_', ' ')}) is currently unavailable. Dominant pollutant and health risk classification will appear once valid observations arrive.
                </>
              )}
            </p>
          </div>

          <div className="pt-3 border-t border-atlas-border dark:border-darkAtlas-border text-[10px] text-atlas-muted dark:text-darkAtlas-muted font-mono flex justify-between">
            <span>Derived from WAQI & Open-Meteo</span>
            <span>Confidence: High</span>
          </div>
        </div>

        {/* Section G: Recent Alerts (3 Cols) */}
        <div className="lg:col-span-3 bg-atlas-surface dark:bg-darkAtlas-surface border border-atlas-border dark:border-darkAtlas-border rounded-xl p-5 shadow-floating dark:shadow-floating-dark space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-atlas-border dark:border-darkAtlas-border pb-2.5">
              <span className="text-xs font-bold text-atlas-text dark:text-darkAtlas-text uppercase tracking-wider flex items-center">
                <BellRing className="w-3.5 h-3.5 mr-1.5 text-atlas-accent dark:text-darkAtlas-accent" />
                Recent Alerts
              </span>
              <span className="text-[10px] font-mono text-atlas-muted dark:text-darkAtlas-muted">
                Active Log
              </span>
            </div>

            <div className="mt-3 space-y-2">
              <div className="p-2.5 bg-atlas-subtle dark:bg-darkAtlas-subtle rounded-lg border border-atlas-border dark:border-darkAtlas-border text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-atlas-text dark:text-darkAtlas-text">{activeCity.name} Monitor</span>
                  <span className="text-[9px] font-mono text-atlas-success dark:text-darkAtlas-success">NOMINAL</span>
                </div>
                <p className="text-[11px] text-atlas-muted dark:text-darkAtlas-muted">
                  No critical particulate thresholds currently breached.
                </p>
              </div>
            </div>
          </div>

          <div className="pt-2">
            <button
              onClick={onNavigateToAlerts}
              className="text-xs font-medium text-atlas-accent dark:text-darkAtlas-accent hover:underline flex items-center space-x-1"
            >
              <span>Manage Alert Rules</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* 5. Lower Section: 24h Predictive Atmospheric Timeline */}
      <ForecastTimeline />
    </div>
  );
};
