import React, { useState, useEffect } from 'react';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { GitCompare, Plus, Trash2, ArrowUpRight, ArrowDownRight, RefreshCw, Radio } from 'lucide-react';

export const CityComparisonView: React.FC = () => {
  const { activeCity, standard } = useAQI();

  // Deduplicate initial city list cleanly:
  const getInitialCities = (current: string) => {
    const defaults = ['Tokyo', 'Delhi', 'London', 'New York'];
    const filtered = defaults.filter((c) => c.toLowerCase() !== current.toLowerCase());
    return [current, filtered[0], filtered[1]];
  };

  const [citiesToCompare, setCitiesToCompare] = useState<string[]>(() => getInitialCities(activeCity.name));
  const [comparisonData, setComparisonData] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [newCityInput, setNewCityInput] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.compareCities(cities, standard);
      setComparisonData(res.comparison || []);
    } catch (e: unknown) {
      console.error(e);
      setErrorMsg('Failed to load comparison data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (citiesToCompare.length > 0) {
      fetchComparison(citiesToCompare);
    }
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

  const handleRemoveCity = (cityToRemove: string) => {
    if (citiesToCompare.length <= 1) return;
    setCitiesToCompare(citiesToCompare.filter((c) => c.toLowerCase() !== cityToRemove.toLowerCase()));
  };

  // Find lowest and highest AQI for relative highlighting
  const validAqis = comparisonData.map((c) => c.aqi).filter((a) => typeof a === 'number');
  const minAqi = validAqis.length > 0 ? Math.min(...validAqis) : null;
  const maxAqi = validAqis.length > 0 ? Math.max(...validAqis) : null;

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
      {!loading && comparisonData.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {comparisonData.map((item, idx) => {
            const isLowest = validAqis.length > 1 && item.aqi === minAqi;
            const isHighest = validAqis.length > 1 && item.aqi === maxAqi;

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
                        onClick={() => handleRemoveCity(item.city)}
                        title="Remove city"
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
                      style={{ color: item.color || '#23966B' }}
                    >
                      {item.aqi !== null && item.aqi !== undefined ? item.aqi : '—'}
                    </span>
                    <div>
                      <span className="text-sm font-semibold text-clima-text dark:text-darkClima-text block font-sans">
                        {item.category || 'Unavailable'}
                      </span>
                      <span className="text-[11px] text-clima-muted dark:text-darkClima-muted font-sans">
                        Dominant:{' '}
                        <span className="text-clima-accent dark:text-darkClima-accent font-mono font-medium">
                          {item.dominant_pollutant || 'N/A'}
                        </span>
                      </span>
                    </div>
                  </div>

                  {/* Concentration Parameter Breakdown */}
                  <div className="mt-5 pt-4 border-t border-clima-border dark:border-darkClima-border space-y-2.5 text-xs font-sans">
                    <div className="flex justify-between items-center text-clima-muted dark:text-darkClima-muted">
                      <span>PM2.5 (Fine Particles):</span>
                      <span className="text-clima-text dark:text-darkClima-text font-mono font-semibold">
                        {item.pm25 !== null && item.pm25 !== undefined ? `${item.pm25} µg/m³` : 'Unavailable'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-clima-muted dark:text-darkClima-muted">
                      <span>PM10 (Coarse Particles):</span>
                      <span className="text-clima-text dark:text-darkClima-text font-mono font-semibold">
                        {item.pm10 !== null && item.pm10 !== undefined ? `${item.pm10} µg/m³` : 'Unavailable'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-clima-muted dark:text-darkClima-muted">
                      <span>NO₂ (Nitrogen Dioxide):</span>
                      <span className="text-clima-text dark:text-darkClima-text font-mono font-semibold">
                        {item.no2 !== null && item.no2 !== undefined ? `${item.no2} µg/m³` : 'Unavailable'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-clima-muted dark:text-darkClima-muted">
                      <span>O₃ (Tropospheric Ozone):</span>
                      <span className="text-clima-text dark:text-darkClima-text font-mono font-semibold">
                        {item.o3 !== null && item.o3 !== undefined ? `${item.o3} µg/m³` : 'Unavailable'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Footer Attribution */}
                <div className="mt-5 pt-3 border-t border-clima-border dark:border-darkClima-border text-[10px] text-clima-muted dark:text-darkClima-muted flex items-center justify-between font-sans">
                  <span className="truncate max-w-[200px]" title={item.primary_source}>
                    {item.primary_source}
                  </span>
                  <span className="px-1.5 py-0.5 rounded bg-clima-subtle dark:bg-darkClima-subtle text-clima-text dark:text-darkClima-text font-mono">
                    {item.is_ground_observation ? 'Ground Sensor' : 'Model Estimate'}
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
                {comparisonData.map((c, i) => (
                  <tr key={i} className="hover:bg-clima-subtle/40 dark:hover:bg-darkClima-subtle/40 transition-colors">
                    <td className="px-4 py-3 font-semibold text-clima-text dark:text-darkClima-text">{c.city}</td>
                    <td className="px-4 py-3 font-mono font-bold" style={{ color: c.color || '#23966B' }}>
                      {c.aqi ?? '—'} ({c.category})
                    </td>
                    <td className="px-4 py-3 font-mono text-clima-text dark:text-darkClima-text">{c.pm25 ?? 'Unavailable'}</td>
                    <td className="px-4 py-3 font-mono text-clima-text dark:text-darkClima-text">{c.pm10 ?? 'Unavailable'}</td>
                    <td className="px-4 py-3 font-mono text-clima-text dark:text-darkClima-text">{c.no2 ?? 'Unavailable'}</td>
                    <td className="px-4 py-3 text-clima-muted dark:text-darkClima-muted">
                      {c.is_ground_observation ? 'Ground Observation' : 'Atmospheric Model'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
