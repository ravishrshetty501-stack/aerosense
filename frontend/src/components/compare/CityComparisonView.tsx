import React, { useState, useEffect, useRef } from 'react';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { CityComparisonItem } from '../../types/airQuality';
import { getAqiScaleColor } from '../../utils/airQualityHelpers';
import { GitCompare, Plus, Trash2, ArrowUpRight, ArrowDownRight, RefreshCw } from 'lucide-react';

function isFiniteNumber(val: unknown): val is number {
  return typeof val === 'number' && Number.isFinite(val);
}

function normalizeFiniteNumber(val: number): number {
  return Object.is(val, -0) ? 0 : val;
}

export function formatComparisonPollutant(
  val: unknown,
  unit: string = '',
  fallback: string = 'Unavailable'
): string {
  if (!isFiniteNumber(val)) return fallback;
  const normalized = normalizeFiniteNumber(val);
  return unit ? `${normalized} ${unit}` : String(normalized);
}

export function computeComparisonAqiBounds(items: CityComparisonItem[]): {
  validCount: number;
  minAqi: number | null;
  maxAqi: number | null;
} {
  const validAqis = items
    .map((c) => c.aqi)
    .filter(isFiniteNumber)
    .map(normalizeFiniteNumber);

  if (validAqis.length === 0) {
    return { validCount: 0, minAqi: null, maxAqi: null };
  }

  return {
    validCount: validAqis.length,
    minAqi: Math.min(...validAqis),
    maxAqi: Math.max(...validAqis),
  };
}

export interface ComparisonItemDisplay {
  hasFiniteAqi: boolean;
  aqiDisplay: number | string;
  aqiColor: string;
  category: string;
  dominantPollutant: string;
  primarySource: string;
  cardSourceLabel: string;
  tableSourceLabel: string;
}

export function resolveComparisonItemDisplay(item: CityComparisonItem): ComparisonItemDisplay {
  const hasFiniteAqi = isFiniteNumber(item.aqi);
  const aqiDisplay = hasFiniteAqi ? normalizeFiniteNumber(item.aqi as number) : '—';
  const aqiColor = hasFiniteAqi
    ? item.color || getAqiScaleColor(item.aqi)
    : '#647570';
  const category = item.category?.trim() ? item.category : 'Unavailable';
  const dominantPollutant = item.dominant_pollutant?.trim() ? item.dominant_pollutant : 'Unavailable';
  const primarySource = item.primary_source?.trim() ? item.primary_source : 'Unavailable';

  const hasAnyFiniteReading =
    hasFiniteAqi || [item.pm25, item.pm10, item.no2, item.o3].some(isFiniteNumber);

  let cardSourceLabel = 'Unavailable';
  let tableSourceLabel = 'Unavailable';
  if (hasAnyFiniteReading) {
    if (item.is_ground_observation) {
      cardSourceLabel = 'Ground Sensor';
      tableSourceLabel = 'Ground Observation';
    } else {
      cardSourceLabel = 'Model Estimate';
      tableSourceLabel = 'Atmospheric Model';
    }
  }

  return {
    hasFiniteAqi,
    aqiDisplay,
    aqiColor,
    category,
    dominantPollutant,
    primarySource,
    cardSourceLabel,
    tableSourceLabel,
  };
}

const COMPARISON_POLLUTANT_ROWS: Array<{
  key: 'pm25' | 'pm10' | 'no2' | 'o3';
  label: string;
}> = [
  { key: 'pm25', label: 'PM2.5 (Fine Particles):' },
  { key: 'pm10', label: 'PM10 (Coarse Particles):' },
  { key: 'no2', label: 'NO₂ (Nitrogen Dioxide):' },
  { key: 'o3', label: 'O₃ (Tropospheric Ozone):' },
];

export const CityComparisonView: React.FC = () => {
  const { activeCity, standard } = useAQI();

  // Deduplicate initial city list cleanly:
  const getInitialCities = (current: string) => {
    const defaults = ['Tokyo', 'Delhi', 'London', 'New York'];
    const filtered = defaults.filter((c) => c.toLowerCase() !== current.toLowerCase());
    return [current, filtered[0], filtered[1]];
  };

  const [citiesToCompare, setCitiesToCompare] = useState<string[]>(() => getInitialCities(activeCity.name));
  const [comparisonData, setComparisonData] = useState<CityComparisonItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [newCityInput, setNewCityInput] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const latestRequestIdRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const resolvedAliasMapRef = useRef<Record<string, string>>({});

  // Sync if active city changes and isn't already present
  useEffect(() => {
    setCitiesToCompare((prev) => {
      const exists = prev.some((c) => c.toLowerCase() === activeCity.name.toLowerCase());
      if (!exists) {
        return [activeCity.name, ...prev.slice(0, 2)];
      }
      return prev;
    });
  }, [activeCity.name]);

  const fetchComparison = async (cities: string[]) => {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const requestId = ++latestRequestIdRef.current;
    setLoading(true);
    setErrorMsg(null);
    setComparisonData([]);
    try {
      const res = await api.compareCities(cities, standard, { signal: controller.signal });
      if (latestRequestIdRef.current !== requestId) return;
      const items = res.comparison || [];
      const aliasMap: Record<string, string> = {};
      items.forEach((item, idx) => {
        if (item?.city && cities[idx]) {
          aliasMap[item.city.trim().toLowerCase()] = cities[idx].trim().toLowerCase();
        }
      });
      resolvedAliasMapRef.current = aliasMap;
      setComparisonData(items);
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') return;
      if (latestRequestIdRef.current !== requestId) return;
      console.error(e);
      setComparisonData([]);
      setErrorMsg('Failed to load comparison data. Please try again.');
    } finally {
      if (latestRequestIdRef.current === requestId) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    if (citiesToCompare.length > 0) {
      fetchComparison(citiesToCompare);
    } else {
      abortControllerRef.current?.abort();
      setComparisonData([]);
      setLoading(false);
    }
    return () => {
      abortControllerRef.current?.abort();
    };
  }, [citiesToCompare, standard]);

  const handleAddCity = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = newCityInput.trim();
    if (!clean) return;

    const alreadyPresent = citiesToCompare.some(
      (c) => c.toLowerCase() === clean.toLowerCase()
    );
    if (alreadyPresent) {
      setErrorMsg(`"${clean}" is already in the comparison.`);
      return;
    }
    if (citiesToCompare.length >= 5) {
      setErrorMsg('You can compare a maximum of 5 cities simultaneously.');
      return;
    }

    setCitiesToCompare([...citiesToCompare, clean]);
    setNewCityInput('');
    setErrorMsg(null);
  };

  const handleRemoveCity = (cityToRemove: string, itemIndex?: number) => {
    if (citiesToCompare.length <= 1) return;
    const normRemove = cityToRemove.trim().toLowerCase();
    const mappedOriginal = resolvedAliasMapRef.current[normRemove];
    const filtered = citiesToCompare.filter(
      (c, idx) =>
        c.trim().toLowerCase() !== normRemove &&
        (!mappedOriginal || c.trim().toLowerCase() !== mappedOriginal) &&
        (itemIndex === undefined || idx !== itemIndex || comparisonData.length !== citiesToCompare.length)
    );
    if (filtered.length > 0 && filtered.length !== citiesToCompare.length) {
      setCitiesToCompare(filtered);
    }
  };

  // Find lowest and highest AQI for relative highlighting
  const { validCount, minAqi, maxAqi } = computeComparisonAqiBounds(comparisonData);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 font-sans">
      {/* Editorial Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-clima-border dark:border-darkClima-border pb-5">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-clima-subtle dark:bg-darkClima-subtle rounded-lg text-clima-accent dark:text-darkClima-accent border border-clima-border dark:border-darkClima-border">
              <GitCompare className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-clima-text dark:text-darkClima-text tracking-tight font-sans">
                Cross-Urban Environmental Comparison
              </h2>
              <p className="text-xs text-clima-muted dark:text-darkClima-muted mt-0.5 font-sans">
                Standardized multi-location comparative analysis calibrated to {standard.replace('_', ' ')} regulatory thresholds.
              </p>
            </div>
          </div>
        </div>

        {/* Add City Form */}
        <div className="flex flex-col items-end">
          <form onSubmit={handleAddCity} className="flex items-center space-x-2 w-full sm:w-auto">
            <input
              type="text"
              placeholder="Add city to compare..."
              value={newCityInput}
              onChange={(e) => {
                setNewCityInput(e.target.value);
                if (errorMsg) setErrorMsg(null);
              }}
              className="bg-clima-surface dark:bg-darkClima-surface border border-clima-border dark:border-darkClima-border rounded-lg px-3.5 py-1.5 text-xs text-clima-text dark:text-darkClima-text placeholder-clima-muted dark:placeholder-darkClima-muted focus:outline-none focus:border-clima-accent dark:focus:border-darkClima-accent font-sans w-48 sm:w-56"
            />
            <button
              type="submit"
              className="px-3.5 py-1.5 bg-clima-accent dark:bg-darkClima-accent hover:opacity-90 text-white dark:text-darkClima-bg rounded-lg text-xs font-medium font-sans flex items-center space-x-1.5 transition-colors shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add</span>
            </button>
          </form>
          {errorMsg && (
            <span className="text-[11px] text-[#C94E55] mt-1 font-sans">{errorMsg}</span>
          )}
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center p-16">
          <RefreshCw className="w-6 h-6 text-clima-accent dark:text-darkClima-accent animate-spin" />
          <span className="ml-3 text-xs text-clima-muted dark:text-darkClima-muted font-sans">
            Retrieving real-time multi-city atmospheric readings...
          </span>
        </div>
      )}

      {/* Comparison Cards Grid */}
      {!loading && errorMsg && comparisonData.length === 0 && (
        <div
          role="alert"
          className="p-6 bg-red-500/10 border border-red-500/30 rounded-xl flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-red-700 dark:text-red-300 font-sans"
        >
          <span>{errorMsg}</span>
          <button
            type="button"
            onClick={() => fetchComparison(citiesToCompare)}
            className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 rounded-lg font-medium transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && comparisonData.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {comparisonData.map((item, idx) => {
            const display = resolveComparisonItemDisplay(item);
            const isLowest = validCount > 1 && display.hasFiniteAqi && display.aqiDisplay === minAqi;
            const isHighest = validCount > 1 && display.hasFiniteAqi && display.aqiDisplay === maxAqi;

            return (
              <div
                key={`${item.city}-${idx}`}
                className="bg-clima-surface dark:bg-darkClima-surface border border-clima-border dark:border-darkClima-border rounded-xl p-5 flex flex-col justify-between hover:border-clima-accent dark:hover:border-darkClima-accent transition-all shadow-floating dark:shadow-floating-dark"
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <h3 className="text-lg font-bold text-clima-text dark:text-darkClima-text font-sans">{item.city}</h3>
                        {isLowest && (
                          <span className="text-[10px] font-medium bg-[#23966B]/15 text-[#23966B] border border-[#23966B]/30 px-2 py-0.5 rounded-full flex items-center">
                            <ArrowDownRight className="w-3 h-3 mr-0.5" /> Cleanest
                          </span>
                        )}
                        {isHighest && (
                          <span className="text-[10px] font-medium bg-[#C94E55]/15 text-[#C94E55] border border-[#C94E55]/30 px-2 py-0.5 rounded-full flex items-center">
                            <ArrowUpRight className="w-3 h-3 mr-0.5" /> Highest Risk
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-clima-muted dark:text-darkClima-muted font-sans">{item.country || 'Global'}</span>
                    </div>

                    {citiesToCompare.length > 1 && (
                      <button
                        onClick={() => handleRemoveCity(item.city, idx)}
                        title="Remove city"
                        aria-label={`Remove ${item.city} from comparison`}
                        className="text-clima-muted dark:text-darkClima-muted hover:text-[#C94E55] p-1.5 rounded-md hover:bg-clima-subtle dark:hover:bg-darkClima-subtle transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>

                  {/* AQI Score & Category */}
                  <div className="mt-5 flex items-baseline space-x-3.5">
                    <span
                      className="text-4xl font-extrabold font-mono tracking-tight"
                      style={{ color: display.aqiColor }}
                    >
                      {display.aqiDisplay}
                    </span>
                    <div>
                      <span className="text-sm font-semibold text-clima-text dark:text-darkClima-text block font-sans">
                        {display.category}
                      </span>
                      <span className="text-[11px] text-clima-muted dark:text-darkClima-muted font-sans">
                        Dominant:{' '}
                        <span className="text-clima-accent dark:text-darkClima-accent font-mono font-medium">
                          {display.dominantPollutant}
                        </span>
                      </span>
                    </div>
                  </div>

                  {/* Concentration Parameter Breakdown */}
                  <div className="mt-5 pt-4 border-t border-clima-border dark:border-darkClima-border space-y-2.5 text-xs font-sans">
                    {COMPARISON_POLLUTANT_ROWS.map((row) => (
                      <div key={row.key} className="flex justify-between items-center text-clima-muted dark:text-darkClima-muted">
                        <span>{row.label}</span>
                        <span className="text-clima-text dark:text-darkClima-text font-mono font-semibold">
                          {formatComparisonPollutant(item[row.key], 'µg/m³')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Footer Attribution */}
                <div className="mt-5 pt-3 border-t border-clima-border dark:border-darkClima-border text-[10px] text-clima-muted dark:text-darkClima-muted flex items-center justify-between font-sans">
                  <span className="truncate max-w-[200px]" title={display.primarySource}>
                    {display.primarySource}
                  </span>
                  <span className="px-1.5 py-0.5 rounded bg-clima-subtle dark:bg-darkClima-subtle text-clima-text dark:text-darkClima-text font-mono">
                    {display.cardSourceLabel}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Cross-City Pollutant Comparison Matrix Table */}
      {!loading && comparisonData.length > 1 && (
        <div className="mt-8 bg-clima-surface dark:bg-darkClima-surface border border-clima-border dark:border-darkClima-border rounded-xl overflow-hidden shadow-floating dark:shadow-floating-dark">
          <div className="px-5 py-3.5 border-b border-clima-border dark:border-darkClima-border bg-clima-subtle/50 dark:bg-darkClima-subtle/50">
            <h4 className="text-xs font-semibold text-clima-text dark:text-darkClima-text uppercase tracking-wider font-sans">
              Parameter Cross-Reference Matrix
            </h4>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-clima-subtle dark:bg-darkClima-subtle text-clima-muted dark:text-darkClima-muted font-mono text-[11px] border-b border-clima-border dark:border-darkClima-border">
                <tr>
                  <th className="px-4 py-3">City</th>
                  <th className="px-4 py-3">{standard.replace('_', ' ')} AQI</th>
                  <th className="px-4 py-3">PM2.5 (µg/m³)</th>
                  <th className="px-4 py-3">PM10 (µg/m³)</th>
                  <th className="px-4 py-3">NO₂ (µg/m³)</th>
                  <th className="px-4 py-3">Source Type</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-clima-border/60 dark:divide-darkClima-border/60 font-sans">
                {comparisonData.map((c, i) => {
                  const display = resolveComparisonItemDisplay(c);
                  return (
                    <tr key={`${c.city}-${i}`} className="hover:bg-clima-subtle/40 dark:hover:bg-darkClima-subtle/40 transition-colors">
                      <td className="px-4 py-3 font-semibold text-clima-text dark:text-darkClima-text">{c.city}</td>
                      <td className="px-4 py-3 font-mono font-bold" style={{ color: display.aqiColor }}>
                        {display.aqiDisplay} ({display.category})
                      </td>
                      <td className="px-4 py-3 font-mono text-clima-text dark:text-darkClima-text">{formatComparisonPollutant(c.pm25)}</td>
                      <td className="px-4 py-3 font-mono text-clima-text dark:text-darkClima-text">{formatComparisonPollutant(c.pm10)}</td>
                      <td className="px-4 py-3 font-mono text-clima-text dark:text-darkClima-text">{formatComparisonPollutant(c.no2)}</td>
                      <td className="px-4 py-3 text-clima-muted dark:text-darkClima-muted">
                        {display.tableSourceLabel}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
