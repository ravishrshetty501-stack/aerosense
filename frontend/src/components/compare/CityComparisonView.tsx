import React, { useState, useEffect } from 'react';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { GitCompare, Plus, Trash2, ShieldCheck, AlertTriangle, RefreshCw } from 'lucide-react';

export const CityComparisonView: React.FC = () => {
  const { activeCity, standard } = useAQI();
  const [citiesToCompare, setCitiesToCompare] = useState<string[]>([activeCity.name, 'London', 'Delhi']);
  const [comparisonData, setComparisonData] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [newCityInput, setNewCityInput] = useState('');

  const fetchComparison = async (cities: string[]) => {
    setLoading(true);
    try {
      const res = await api.compareCities(cities, standard);
      setComparisonData(res.comparison || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchComparison(citiesToCompare);
  }, [citiesToCompare, standard]);

  const handleAddCity = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCityInput.trim() || citiesToCompare.includes(newCityInput.trim())) return;
    if (citiesToCompare.length >= 5) {
      alert('Maximum 5 cities can be compared simultaneously.');
      return;
    }
    const updated = [...citiesToCompare, newCityInput.trim()];
    setCitiesToCompare(updated);
    setNewCityInput('');
  };

  const handleRemoveCity = (city: string) => {
    if (citiesToCompare.length <= 1) return;
    setCitiesToCompare(citiesToCompare.filter((c) => c !== city));
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header & City Add Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <GitCompare className="w-5 h-5 text-cyanAccent" />
            <h2 className="text-xl font-bold tracking-tight text-white font-mono">
              Cross-Urban Environmental Comparison Terminal
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Standardized multi-city comparison using consistent measurement units and official {standard} breakpoints.
          </p>
        </div>

        {/* Add City Input */}
        <form onSubmit={handleAddCity} className="flex items-center space-x-2">
          <input
            type="text"
            placeholder="Add city to compare..."
            value={newCityInput}
            onChange={(e) => setNewCityInput(e.target.value)}
            className="bg-navy-950 border border-slate-700 rounded-md px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyanAccent font-mono"
          />
          <button
            type="submit"
            className="px-3 py-1.5 bg-navy-850 hover:bg-navy-800 border border-slate-700 text-cyanAccent rounded-md text-xs font-mono flex items-center space-x-1"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add</span>
          </button>
        </form>
      </div>

      {loading && (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="w-6 h-6 text-cyanAccent animate-spin" />
          <span className="ml-2 text-xs font-mono text-slate-400">Loading multi-city atmospheric readings...</span>
        </div>
      )}

      {/* Comparison Grid */}
      {!loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {comparisonData.map((item, idx) => (
            <div
              key={idx}
              className="card-metric rounded-lg p-5 terminal-border relative overflow-hidden flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-bold text-white font-mono">{item.city}</h3>
                    <span className="text-xs text-slate-400">{item.country || 'Global'}</span>
                  </div>
                  {citiesToCompare.length > 1 && (
                    <button
                      onClick={() => handleRemoveCity(item.city)}
                      title="Remove city"
                      className="text-slate-500 hover:text-red-400 p-1"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>

                <div className="mt-4 flex items-baseline space-x-3">
                  <span className="text-4xl font-bold font-mono" style={{ color: item.color || '#10b981' }}>
                    {item.aqi !== null ? item.aqi : '—'}
                  </span>
                  <div>
                    <span className="text-xs font-semibold text-slate-200 block">{item.category}</span>
                    <span className="text-[10px] font-mono text-slate-400">
                      Dominant: <span className="text-cyanAccent">{item.dominant_pollutant || 'N/A'}</span>
                    </span>
                  </div>
                </div>

                {/* Pollutant Metrics Table */}
                <div className="mt-4 pt-3 border-t border-slate-800 space-y-2 text-xs font-mono">
                  <div className="flex justify-between text-slate-400">
                    <span>PM2.5 Concentration:</span>
                    <span className="text-slate-200 font-bold">{item.pm25 !== null ? `${item.pm25} µg/m³` : 'N/A'}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>PM10 Concentration:</span>
                    <span className="text-slate-200 font-bold">{item.pm10 !== null ? `${item.pm10} µg/m³` : 'N/A'}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>NO₂ Concentration:</span>
                    <span className="text-slate-200 font-bold">{item.no2 !== null ? `${item.no2} µg/m³` : 'N/A'}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>O₃ Concentration:</span>
                    <span className="text-slate-200 font-bold">{item.o3 !== null ? `${item.o3} µg/m³` : 'N/A'}</span>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-2 border-t border-slate-800/80 text-[10px] font-mono text-slate-500 flex items-center justify-between">
                <span className="truncate max-w-[180px]">{item.primary_source}</span>
                <span>{item.is_ground_observation ? 'Ground' : 'Model'}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
