import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { Layers, MapPin, Radio, Compass, RefreshCw } from 'lucide-react';

export const GlobalPollutionMap: React.FC = () => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const { activeCity, setActiveCity, popularCities } = useAQI();
  const [selectedStation, setSelectedStation] = useState<any | null>(null);
  const [filterPollutant, setFilterPollutant] = useState<string>('all');
  const [loadingStations, setLoadingStations] = useState<boolean>(false);
  const [nearbyStations, setNearbyStations] = useState<any[]>([]);

  // Initialize MapLibre
  useEffect(() => {
    if (!mapContainer.current) return;

    // Use CartoDB Dark Matter raster tiles (free, dark-themed, scientific)
    const mapInstance = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'carto-dark': {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
              'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
              'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
            ],
            tileSize: 256,
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
          },
        },
        layers: [
          {
            id: 'carto-dark-layer',
            type: 'raster',
            source: 'carto-dark',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: [activeCity.longitude, activeCity.latitude],
      zoom: 6,
    });

    mapInstance.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right');
    map.current = mapInstance;

    return () => {
      mapInstance.remove();
    };
  }, []);

  // Pan to active city when changed & add city marker
  useEffect(() => {
    if (!map.current) return;
    map.current.flyTo({
      center: [activeCity.longitude, activeCity.latitude],
      zoom: 7,
      essential: true,
    });

    // Fetch stations around active city
    setLoadingStations(true);
    api.getNearbyStations(activeCity.latitude, activeCity.longitude)
      .then((stations) => {
        setNearbyStations(stations);
      })
      .catch(console.error)
      .finally(() => setLoadingStations(false));
  }, [activeCity]);

  // Render markers for popular cities and nearby stations
  useEffect(() => {
    if (!map.current) return;

    const markers: maplibregl.Marker[] = [];

    // Add city terminal markers
    popularCities.forEach((city) => {
      const el = document.createElement('div');
      el.className = 'city-map-marker';
      el.style.width = '14px';
      el.style.height = '14px';
      el.style.borderRadius = '50%';
      el.style.border = '2px solid #00f2fe';
      el.style.backgroundColor = city.name === activeCity.name ? '#00f2fe' : '#0b1329';
      el.style.cursor = 'pointer';
      el.style.boxShadow = '0 0 10px rgba(0, 242, 254, 0.5)';

      const marker = new maplibregl.Marker(el)
        .setLngLat([city.longitude, city.latitude])
        .setPopup(
          new maplibregl.Popup({ offset: 15 }).setHTML(`
            <div style="font-family: monospace; font-size: 11px;">
              <strong style="color: #00f2fe; font-size: 13px;">${city.name}</strong><br/>
              <span>${city.country || ''}</span><br/>
              <span style="color: #94a3b8;">Lat: ${city.latitude.toFixed(2)}°, Lon: ${city.longitude.toFixed(2)}°</span>
            </div>
          `)
        )
        .addTo(map.current!);

      el.addEventListener('click', () => {
        setActiveCity(city);
      });

      markers.push(marker);
    });

    // Add ground station markers
    nearbyStations.forEach((st) => {
      if (!st.latitude || !st.longitude) return;

      const el = document.createElement('div');
      el.style.width = '10px';
      el.style.height = '10px';
      el.style.borderRadius = '50%';
      el.style.backgroundColor = '#10b981';
      el.style.border = '1px solid #ffffff';
      el.style.cursor = 'pointer';

      const marker = new maplibregl.Marker(el)
        .setLngLat([st.longitude, st.latitude])
        .setPopup(
          new maplibregl.Popup({ offset: 15 }).setHTML(`
            <div style="font-family: monospace; font-size: 11px;">
              <span style="color: #10b981; font-weight: bold;">Ground Sensor Station</span><br/>
              <strong>${st.name}</strong><br/>
              <span style="color: #94a3b8;">Provider: ${st.provider || 'OpenAQ'}</span>
            </div>
          `)
        )
        .addTo(map.current!);

      el.addEventListener('click', () => {
        setSelectedStation(st);
      });

      markers.push(marker);
    });

    return () => {
      markers.forEach((m) => m.remove());
    };
  }, [popularCities, nearbyStations, activeCity, setActiveCity]);

  return (
    <div className="relative w-full h-[calc(100vh-8rem)] rounded-lg overflow-hidden border border-surface-border">
      {/* MapLibre DOM Container */}
      <div ref={mapContainer} className="w-full h-full" />

      {/* Map Control Bar Overlay */}
      <div className="absolute top-4 left-4 z-10 bg-navy-900/90 backdrop-blur-md border border-slate-700/80 rounded-lg p-3 max-w-xs space-y-3 shadow-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Compass className="w-4 h-4 text-cyanAccent" />
            <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              Scientific Spatial Grid
            </h3>
          </div>
          {loadingStations && <RefreshCw className="w-3.5 h-3.5 text-cyanAccent animate-spin" />}
        </div>

        <p className="text-[11px] text-slate-400">
          Viewing ground-level physical stations and atmospheric spatial nodes around <span className="text-cyanAccent font-medium">{activeCity.name}</span>.
        </p>

        {/* Legend */}
        <div className="pt-2 border-t border-slate-800 space-y-1.5 text-[10px] font-mono">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyanAccent border border-navy-950 inline-block shadow-sm"></span>
            <span className="text-slate-300">Selected Terminal ({activeCity.name})</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block"></span>
            <span className="text-slate-300">OpenAQ Physical Ground Sensors ({nearbyStations.length})</span>
          </div>
        </div>
      </div>

      {/* Station Details Drawer when selected */}
      {selectedStation && (
        <div className="absolute bottom-4 right-4 z-10 bg-navy-900/95 backdrop-blur-md border border-slate-700 rounded-lg p-4 max-w-sm shadow-2xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-emerald-400 flex items-center">
              <Radio className="w-3 h-3 mr-1" /> Physical Station
            </span>
            <button
              onClick={() => setSelectedStation(null)}
              className="text-slate-400 hover:text-white text-xs"
            >
              ✕
            </button>
          </div>
          <h4 className="text-sm font-bold text-white font-mono">{selectedStation.name}</h4>
          <p className="text-xs text-slate-400">
            Coordinates: {selectedStation.latitude?.toFixed(4)}°, {selectedStation.longitude?.toFixed(4)}°
          </p>
          <div className="text-[11px] font-mono text-slate-300 pt-1 border-t border-slate-800">
            Source: {selectedStation.provider || 'OpenAQ Network'}
          </div>
        </div>
      )}
    </div>
  );
};
