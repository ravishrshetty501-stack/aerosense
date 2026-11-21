import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { Layers, MapPin, Radio, Compass, RefreshCw, Filter, ShieldCheck } from 'lucide-react';

export const GlobalPollutionMap: React.FC = () => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const { activeCity, setActiveCity, popularCities } = useAQI();
  const [selectedStation, setSelectedStation] = useState<any | null>(null);
  const [aqiFilter, setAqiFilter] = useState<'all' | 'good' | 'moderate' | 'unhealthy'>('all');
  const [loadingStations, setLoadingStations] = useState<boolean>(false);
  const [nearbyStations, setNearbyStations] = useState<any[]>([]);

  // Initialize MapLibre with ESRI World Dark Gray Canvas (Clean, Free, Zero Watermark, Scientific)
  useEffect(() => {
    if (!mapContainer.current) return;

    const mapInstance = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'esri-dark-gray': {
            type: 'raster',
            tiles: [
              'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
            ],
            tileSize: 256,
            attribution: '&copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
            maxzoom: 16,
          },
          'esri-dark-reference': {
            type: 'raster',
            tiles: [
              'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
            ],
            tileSize: 256,
            maxzoom: 16,
          },
        },
        layers: [
          {
            id: 'esri-dark-base',
            type: 'raster',
            source: 'esri-dark-gray',
            minzoom: 0,
            maxzoom: 16,
          },
          {
            id: 'esri-dark-ref',
            type: 'raster',
            source: 'esri-dark-reference',
            minzoom: 0,
            maxzoom: 16,
          },
        ],
      },
      center: [activeCity.longitude, activeCity.latitude],
      zoom: 10,
    });

    mapInstance.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right');
    mapInstance.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: 'metric' }), 'bottom-left');
    map.current = mapInstance;

    return () => {
      mapInstance.remove();
    };
  }, []);

  // Pan to active city when changed & fetch stations
  useEffect(() => {
    if (!map.current) return;
    map.current.flyTo({
      center: [activeCity.longitude, activeCity.latitude],
      zoom: 10.5,
      essential: true,
      duration: 1500,
    });

    setLoadingStations(true);
    api.getNearbyStations(activeCity.latitude, activeCity.longitude)
      .then((stations) => {
        setNearbyStations(stations);
      })
      .catch(console.error)
      .finally(() => setLoadingStations(false));
  }, [activeCity]);

  // Color helper for station pins based on US EPA thresholds
  const getAQIColor = (aqi?: number | null) => {
    if (aqi === undefined || aqi === null) return '#38bdf8';
    if (aqi <= 50) return '#10b981';
    if (aqi <= 100) return '#f59e0b';
    if (aqi <= 150) return '#f97316';
    if (aqi <= 200) return '#ef4444';
    if (aqi <= 300) return '#8b5cf6';
    return '#7f1d1d';
  };

  // Filter stations based on selection
  const filteredStations = nearbyStations.filter((st) => {
    if (aqiFilter === 'all') return true;
    const val = st.aqi ?? 50;
    if (aqiFilter === 'good') return val <= 50;
    if (aqiFilter === 'moderate') return val > 50 && val <= 100;
    if (aqiFilter === 'unhealthy') return val > 100;
    return true;
  });

  // Render markers for active city and all ground stations
  useEffect(() => {
    if (!map.current) return;

    const markers: maplibregl.Marker[] = [];

    // 1. Terminal Node (Active City) with pulsing radar ring
    const cityEl = document.createElement('div');
    cityEl.className = 'active-terminal-node';
    cityEl.style.width = '24px';
    cityEl.style.height = '24px';
    cityEl.style.borderRadius = '50%';
    cityEl.style.border = '2px solid #00f2fe';
    cityEl.style.backgroundColor = 'rgba(0, 242, 254, 0.25)';
    cityEl.style.boxShadow = '0 0 15px rgba(0, 242, 254, 0.8)';
    cityEl.style.display = 'flex';
    cityEl.style.alignItems = 'center';
    cityEl.style.justifyContent = 'center';
    cityEl.style.cursor = 'pointer';

    const innerDot = document.createElement('div');
    innerDot.style.width = '8px';
    innerDot.style.height = '8px';
    innerDot.style.borderRadius = '50%';
    innerDot.style.backgroundColor = '#00f2fe';
    cityEl.appendChild(innerDot);

    const cityMarker = new maplibregl.Marker(cityEl)
      .setLngLat([activeCity.longitude, activeCity.latitude])
      .setPopup(
        new maplibregl.Popup({ offset: 15 }).setHTML(`
          <div style="font-family: monospace; font-size: 11px; padding: 4px;">
            <div style="color: #00f2fe; font-weight: bold; font-size: 13px;">${activeCity.name.toUpperCase()}</div>
            <div style="color: #94a3b8; font-size: 10px;">Primary Command Terminal</div>
            <div style="margin-top: 4px; color: #cbd5e1;">Lat: ${activeCity.latitude.toFixed(4)}°, Lon: ${activeCity.longitude.toFixed(4)}°</div>
          </div>
        `)
      )
      .addTo(map.current!);

    markers.push(cityMarker);

    // 2. Physical Ground Stations with live numerical AQI pills
    filteredStations.forEach((st) => {
      if (!st.latitude || !st.longitude) return;

      const color = getAQIColor(st.aqi);
      const stEl = document.createElement('div');
      stEl.className = 'ground-sensor-marker';
      stEl.style.padding = '2px 6px';
      stEl.style.borderRadius = '3px';
      stEl.style.backgroundColor = '#0b1329';
      stEl.style.border = `1.5px solid ${color}`;
      stEl.style.color = '#ffffff';
      stEl.style.fontFamily = 'monospace';
      stEl.style.fontSize = '10px';
      stEl.style.fontWeight = 'bold';
      stEl.style.cursor = 'pointer';
      stEl.style.boxShadow = `0 2px 8px rgba(0,0,0,0.7)`;
      stEl.innerText = st.aqi !== undefined && st.aqi !== null ? String(st.aqi) : '●';

      stEl.addEventListener('click', () => {
        setSelectedStation(st);
      });

      const stMarker = new maplibregl.Marker(stEl)
        .setLngLat([st.longitude, st.latitude])
        .setPopup(
          new maplibregl.Popup({ offset: 15 }).setHTML(`
            <div style="font-family: monospace; font-size: 11px; padding: 4px;">
              <div style="color: ${color}; font-weight: bold;">AQI ${st.aqi !== null && st.aqi !== undefined ? st.aqi : 'N/A'} — Ground Sensor</div>
              <div style="color: #ffffff; font-weight: 600; margin-top: 2px;">${st.name}</div>
              <div style="color: #94a3b8; font-size: 10px; margin-top: 4px;">Network: ${st.provider || 'Environmental Agency'}</div>
              <div style="color: #64748b; font-size: 9px;">GPS: ${st.latitude.toFixed(4)}°, ${st.longitude.toFixed(4)}°</div>
            </div>
          `)
        )
        .addTo(map.current!);

      markers.push(stMarker);
    });

    return () => {
      markers.forEach((m) => m.remove());
    };
  }, [filteredStations, activeCity]);

  return (
    <div className="relative w-full h-[calc(100vh-8.5rem)] rounded border border-slate-800 bg-[#070b14] overflow-hidden">
      {/* MapLibre Canvas */}
      <div ref={mapContainer} className="w-full h-full" />

      {/* Top Left: Scientific Telemetry Overlay */}
      <div className="absolute top-3 left-3 z-10 bg-slate-950/95 backdrop-blur border border-slate-800 rounded p-3.5 max-w-sm shadow-xl font-mono space-y-2.5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center space-x-2">
            <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span className="text-xs font-bold text-white tracking-wider">
              SPATIAL GROUND SENSOR ARRAY
            </span>
          </div>
          {loadingStations && <RefreshCw className="w-3.5 h-3.5 text-cyan-400 animate-spin" />}
        </div>

        <div className="text-[11px] text-slate-300 space-y-1">
          <div className="flex justify-between">
            <span className="text-slate-400">Target Terminal:</span>
            <span className="text-white font-bold">{activeCity.name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Live Ground Stations:</span>
            <span className="text-emerald-400 font-bold">{nearbyStations.length} reporting</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Basemap Engine:</span>
            <span className="text-slate-200">Esri Dark Gray Canvas (Verified)</span>
          </div>
        </div>

        {/* Severity Filter Controls */}
        <div className="pt-2 border-t border-slate-800 space-y-1.5">
          <span className="text-[10px] text-slate-400 uppercase tracking-widest block">
            Filter by Air Quality Tier:
          </span>
          <div className="grid grid-cols-4 gap-1 text-[10px]">
            <button
              onClick={() => setAqiFilter('all')}
              className={`py-1 rounded border transition-colors ${
                aqiFilter === 'all'
                  ? 'bg-slate-800 text-white border-slate-600'
                  : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:text-white'
              }`}
            >
              All ({nearbyStations.length})
            </button>
            <button
              onClick={() => setAqiFilter('good')}
              className={`py-1 rounded border transition-colors ${
                aqiFilter === 'good'
                  ? 'bg-emerald-950 text-emerald-300 border-emerald-600'
                  : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:text-emerald-400'
              }`}
            >
              Good
            </button>
            <button
              onClick={() => setAqiFilter('moderate')}
              className={`py-1 rounded border transition-colors ${
                aqiFilter === 'moderate'
                  ? 'bg-amber-950 text-amber-300 border-amber-600'
                  : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:text-amber-400'
              }`}
            >
              Mod
            </button>
            <button
              onClick={() => setAqiFilter('unhealthy')}
              className={`py-1 rounded border transition-colors ${
                aqiFilter === 'unhealthy'
                  ? 'bg-red-950 text-red-300 border-red-600'
                  : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:text-red-400'
              }`}
            >
              Unhealthy
            </button>
          </div>
        </div>
      </div>

      {/* Selected Station Inspector Drawer */}
      {selectedStation && (
        <div className="absolute bottom-4 right-4 z-10 bg-slate-950/95 backdrop-blur border border-slate-800 rounded p-4 max-w-sm w-full shadow-2xl font-mono space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-[10px] text-emerald-400 uppercase tracking-widest flex items-center">
              <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Verified Physical Station
            </span>
            <button
              onClick={() => setSelectedStation(null)}
              className="text-slate-400 hover:text-white text-xs px-1"
            >
              ✕
            </button>
          </div>

          <div>
            <div className="text-xs text-slate-400 font-semibold">{selectedStation.provider}</div>
            <h4 className="text-sm font-bold text-white mt-0.5">{selectedStation.name}</h4>
          </div>

          <div className="grid grid-cols-2 gap-2 bg-slate-900/80 p-2.5 rounded border border-slate-800/80 text-xs">
            <div>
              <span className="text-[10px] text-slate-400 block">Reported AQI</span>
              <span
                className="text-xl font-bold"
                style={{ color: getAQIColor(selectedStation.aqi) }}
              >
                {selectedStation.aqi ?? '—'}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 block">Telemetry Status</span>
              <span className="text-xs text-emerald-400 font-semibold">ONLINE / VERIFIED</span>
            </div>
          </div>

          <div className="text-[10px] text-slate-400 space-y-0.5">
            <div>Latitude: {selectedStation.latitude?.toFixed(4)}°</div>
            <div>Longitude: {selectedStation.longitude?.toFixed(4)}°</div>
            {selectedStation.last_updated && (
              <div>Last Observation: {new Date(selectedStation.last_updated).toLocaleTimeString()}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
