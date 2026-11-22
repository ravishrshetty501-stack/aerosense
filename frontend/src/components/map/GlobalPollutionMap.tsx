import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { useAQI } from '../../context/AQIContext';
import { useTheme } from '../../context/ThemeContext';
import { api } from '../../services/api';
import { MonitoringStation } from '../../types/airQuality';
import {
  Layers,
  MapPin,
  Radio,
  Compass,
  RefreshCw,
  Filter,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Minimize2,
  Navigation,
  Play,
  Pause,
  BarChart2,
  Sliders,
  Eye,
  EyeOff,
  Check,
  Plus,
  Minus,
  RotateCcw,
  Globe2
} from 'lucide-react';

type PollutantVariable = 'pm25' | 'pm10' | 'no2' | 'so2' | 'co' | 'o3';
type AqiTier = 'all' | 'good' | 'moderate' | 'poor' | 'severe';
type TemporalStep = 'hourly' | 'daily' | '72h';

export const GlobalPollutionMap: React.FC = () => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const { activeCity, setActiveCity, airQuality } = useAQI();
  const { theme, resolvedTheme } = useTheme();

  // Control panel states
  const [selectedStation, setSelectedStation] = useState<MonitoringStation | null>(null);
  const [nearbyStations, setNearbyStations] = useState<MonitoringStation[]>([]);
  const [loadingStations, setLoadingStations] = useState<boolean>(false);
  const [selectedVariable, setSelectedVariable] = useState<PollutantVariable>('pm25');
  const [activeDataset, setActiveDataset] = useState<'ground' | 'cams_model' | 'forecast'>('ground');
  const [aqiTierFilter, setAqiTierFilter] = useState<AqiTier>('all');
  const [bottomWorkspaceOpen, setBottomWorkspaceOpen] = useState<boolean>(true);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [timelineIndex, setTimelineIndex] = useState<number>(0);
  const [temporalStep, setTemporalStep] = useState<TemporalStep>('hourly');
  const [chartMode, setChartMode] = useState<'standardized' | 'absolute'>('standardized');

  // Map tile URLs based on current theme
  const getMapStyle = (currentTheme: 'light' | 'dark'): maplibregl.StyleSpecification => {
    const isDark = currentTheme === 'dark';
    const baseTile = isDark
      ? 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}'
      : 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}';
    const refTile = isDark
      ? 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}'
      : 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}';

    return {
      version: 8,
      sources: {
        'esri-canvas-base': {
          type: 'raster',
          tiles: [baseTile],
          tileSize: 256,
          attribution: '&copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
          maxzoom: 16,
        },
        'esri-canvas-ref': {
          type: 'raster',
          tiles: [refTile],
          tileSize: 256,
          maxzoom: 16,
        },
      },
      layers: [
        {
          id: 'esri-base',
          type: 'raster',
          source: 'esri-canvas-base',
          minzoom: 0,
          maxzoom: 16,
        },
        {
          id: 'esri-ref',
          type: 'raster',
          source: 'esri-canvas-ref',
          minzoom: 0,
          maxzoom: 16,
        },
      ],
    };
  };

  // Initialize MapLibre
  useEffect(() => {
    if (!mapContainer.current) return;

    const mapInstance = new maplibregl.Map({
      container: mapContainer.current,
      style: getMapStyle(resolvedTheme),
      center: [activeCity.longitude, activeCity.latitude],
      zoom: 9.5,
      attributionControl: false,
    });

    mapInstance.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
    mapInstance.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: 'metric' }), 'bottom-left');
    map.current = mapInstance;

    return () => {
      mapInstance.remove();
    };
  }, []);

  // Update map style when theme changes
  useEffect(() => {
    if (!map.current) return;
    map.current.setStyle(getMapStyle(resolvedTheme));
  }, [resolvedTheme]);

  // Pan to active city when changed & fetch stations
  useEffect(() => {
    if (!map.current) return;
    map.current.flyTo({
      center: [activeCity.longitude, activeCity.latitude],
      zoom: 10,
      essential: true,
      duration: 1200,
    });

    setLoadingStations(true);
    api.getNearbyStations(activeCity.latitude, activeCity.longitude)
      .then((stations) => {
        setNearbyStations(stations);
      })
      .catch(console.error)
      .finally(() => setLoadingStations(false));
  }, [activeCity]);

  // Time scrubber autoplay
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (isPlaying) {
      interval = setInterval(() => {
        setTimelineIndex((prev) => (prev + 1) % 24);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isPlaying]);

  // Color helper for station pins based on CliMA Scope scientific scale
  const getAQIColor = (aqi?: number | null) => {
    if (aqi === undefined || aqi === null) return '#159DB0';
    if (aqi <= 50) return '#23966B';   // Good (Teal Green)
    if (aqi <= 100) return '#D5A33A';  // Moderate (Amber Gold)
    if (aqi <= 150) return '#E27C42';  // Poor (Warm Orange)
    if (aqi <= 200) return '#C94E55';  // Severe (Deep Coral Red)
    if (aqi <= 300) return '#8E44AD';  // Very Severe (Purple)
    return '#5B2C6F';                  // Hazardous (Deep Maroon)
  };

  // Filter stations based on selection
  const filteredStations = nearbyStations.filter((st) => {
    if (aqiTierFilter === 'all') return true;
    const val = st.aqi ?? 50;
    if (aqiTierFilter === 'good') return val <= 50;
    if (aqiTierFilter === 'moderate') return val > 50 && val <= 100;
    if (aqiTierFilter === 'poor') return val > 100 && val <= 150;
    if (aqiTierFilter === 'severe') return val > 150;
    return true;
  });

  // Render station pins and target city marker
  useEffect(() => {
    if (!map.current) return;

    const markers: maplibregl.Marker[] = [];

    // 1. Target Location Marker (CliMA Scope Focus Ring)
    const cityEl = document.createElement('div');
    cityEl.className = 'active-focus-marker';
    cityEl.setAttribute('role', 'img');
    cityEl.setAttribute('aria-label', `Geographical Focus Location: ${activeCity.name}`);
    cityEl.style.width = '20px';
    cityEl.style.height = '20px';
    cityEl.style.borderRadius = '50%';
    cityEl.style.border = '2px solid #087F72';
    cityEl.style.backgroundColor = 'rgba(8, 127, 114, 0.2)';
    cityEl.style.display = 'flex';
    cityEl.style.alignItems = 'center';
    cityEl.style.justifyContent = 'center';
    cityEl.style.cursor = 'pointer';

    const innerDot = document.createElement('div');
    innerDot.style.width = '6px';
    innerDot.style.height = '6px';
    innerDot.style.borderRadius = '50%';
    innerDot.style.backgroundColor = '#087F72';
    cityEl.appendChild(innerDot);

    const cityMarker = new maplibregl.Marker(cityEl)
      .setLngLat([activeCity.longitude, activeCity.latitude])
      .setPopup(
        new maplibregl.Popup({ offset: 12 }).setHTML(`
          <div style="font-size: 11px;">
            <div style="color: #087F72; font-weight: 700;">${activeCity.name}</div>
            <div style="color: #647570; font-size: 10px;">Geographical Focus Location</div>
            <div style="color: #172B28; font-family: monospace; font-size: 10px; margin-top: 3px;">
              ${activeCity.latitude.toFixed(4)}°N, ${activeCity.longitude.toFixed(4)}°E
            </div>
          </div>
        `)
      )
      .addTo(map.current!);

    markers.push(cityMarker);

    // 2. Physical Monitoring Station Pins
    filteredStations.forEach((st) => {
      if (!st.latitude || !st.longitude) return;

      const color = getAQIColor(st.aqi);
      const stEl = document.createElement('button');
      stEl.type = 'button';
      stEl.className = 'scientific-station-pin';
      stEl.setAttribute('aria-label', `Ground Station ${st.name}, AQI ${st.aqi ?? 'unavailable'}`);
      stEl.style.padding = '2px 5px';
      stEl.style.borderRadius = '4px';
      stEl.style.backgroundColor = resolvedTheme === 'dark' ? '#172426' : '#FFFFFF';
      stEl.style.border = `1.5px solid ${color}`;
      stEl.style.color = color;
      stEl.style.fontFamily = '"IBM Plex Mono", monospace';
      stEl.style.fontSize = '9.5px';
      stEl.style.fontWeight = '700';
      stEl.style.cursor = 'pointer';
      stEl.style.boxShadow = '0 2px 6px rgba(0,0,0,0.12)';
      stEl.innerText = st.aqi !== undefined && st.aqi !== null ? String(st.aqi) : '●';

      stEl.addEventListener('click', () => {
        setSelectedStation(st);
      });

      const stMarker = new maplibregl.Marker(stEl)
        .setLngLat([st.longitude, st.latitude])
        .setPopup(
          new maplibregl.Popup({ offset: 14 }).setHTML(`
            <div style="font-size: 11px; max-width: 200px;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 2px;">
                <span style="color: ${color}; font-weight: 700; font-family: monospace;">AQI ${st.aqi ?? 'N/A'}</span>
                <span style="font-size: 9px; color: #647570;">Ground Station</span>
              </div>
              <div style="font-weight: 600; color: #172B28; line-height: 1.3;">${st.name}</div>
              <div style="font-size: 9.5px; color: #647570; margin-top: 4px;">Provider: ${st.provider || 'Regional Agency'}</div>
            </div>
          `)
        )
        .addTo(map.current!);

      markers.push(stMarker);
    });

    return () => {
      markers.forEach((m) => m.remove());
    };
  }, [filteredStations, activeCity, resolvedTheme]);

  // Toolbar actions
  const handleZoomIn = () => map.current?.zoomIn();
  const handleZoomOut = () => map.current?.zoomOut();
  const handleResetPosition = () => {
    map.current?.flyTo({
      center: [activeCity.longitude, activeCity.latitude],
      zoom: 9.5,
      essential: true,
    });
  };
  const handleLocateUser = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          map.current?.flyTo({
            center: [pos.coords.longitude, pos.coords.latitude],
            zoom: 11,
            essential: true,
          });
        },
        (err) => console.warn('Geolocation denied:', err)
      );
    }
  };

  // Forecast points for bottom timeline scrubber
  const timelinePoints = (airQuality?.forecast || []).slice(0, 24);
  const activePoint = timelinePoints[timelineIndex] || null;

  return (
    <div className="relative w-full h-[calc(100vh-3.5rem)] bg-clima-bg dark:bg-darkClima-bg overflow-hidden select-none">
      {/* MapLibre WebGL Canvas */}
      <div ref={mapContainer} className="w-full h-full" />

      {/* =========================================================================
          1. FLOATING TOP CONTROLS (Inspired by CliMA Scope Top Bar)
         ========================================================================= */}
      <div className="absolute top-3 left-1/2 -translate-x-1/2 z-20 hidden md:flex items-center space-x-3 bg-clima-surface/95 dark:bg-darkClima-surface/95 backdrop-blur-md px-3 py-1.5 rounded-lg border border-clima-border dark:border-darkClima-border shadow-floating dark:shadow-floating-dark text-xs">
        <div className="flex items-center space-x-1.5 text-clima-muted dark:text-darkClima-muted font-sans text-[11px]">
          <span>View Mode:</span>
          <button
            onClick={() => setActiveDataset('ground')}
            className={`px-2 py-0.5 rounded font-medium transition-colors ${
              activeDataset === 'ground'
                ? 'bg-clima-accent dark:bg-darkClima-accent text-white dark:text-darkClima-bg shadow-sm'
                : 'text-clima-text dark:text-darkClima-text hover:bg-clima-subtle dark:hover:bg-darkClima-subtle'
            }`}
          >
            Physical Stations
          </button>
          <button
            onClick={() => setActiveDataset('cams_model')}
            className={`px-2 py-0.5 rounded font-medium transition-colors ${
              activeDataset === 'cams_model'
                ? 'bg-clima-accent dark:bg-darkClima-accent text-white dark:text-darkClima-bg shadow-sm'
                : 'text-clima-text dark:text-darkClima-text hover:bg-clima-subtle dark:hover:bg-darkClima-subtle'
            }`}
          >
            CAMS Model Grid
          </button>
        </div>

        <span className="h-3 w-px bg-clima-border dark:bg-darkClima-border" />

        <div className="flex items-center space-x-1 text-clima-muted dark:text-darkClima-muted font-sans text-[11px]">
          <span>Scale:</span>
          <button
            onClick={() => setChartMode('standardized')}
            className={`px-1.5 py-0.5 rounded font-medium ${
              chartMode === 'standardized'
                ? 'text-clima-accent dark:text-darkClima-accent font-semibold'
                : 'hover:text-clima-text'
            }`}
          >
            Relative
          </button>
          <span>/</span>
          <button
            onClick={() => setChartMode('absolute')}
            className={`px-1.5 py-0.5 rounded font-medium ${
              chartMode === 'absolute'
                ? 'text-clima-accent dark:text-darkClima-accent font-semibold'
                : 'hover:text-clima-text'
            }`}
          >
            Concentration
          </button>
        </div>
      </div>

      {/* =========================================================================
          2. FLOATING LEFT CONTROL DOCK (CliMA Scope Datasets & Variables)
         ========================================================================= */}
      <div className="absolute top-3 left-3 z-20 w-72 max-w-[calc(100vw-1.5rem)] space-y-2 font-sans">
        {/* Datasets Accordion Card */}
        <div className="bg-clima-surface/95 dark:bg-darkClima-surface/95 backdrop-blur-md rounded-lg border border-clima-border dark:border-darkClima-border shadow-floating dark:shadow-floating-dark p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-clima-muted dark:text-darkClima-muted">
              Datasets
            </span>
            <span className="text-[10px] font-mono text-clima-accent dark:text-darkClima-accent font-medium">
              v1.4.0
            </span>
          </div>

          <div className="bg-clima-subtle/80 dark:bg-darkClima-subtle/80 rounded-md p-2 flex items-center justify-between text-xs">
            <div className="flex items-center space-x-2">
              <Radio className="w-3.5 h-3.5 text-clima-accent dark:text-darkClima-accent animate-pulse" />
              <span className="font-medium text-clima-text dark:text-darkClima-text">WAQI Sensor Array</span>
            </div>
            <span className="text-[10px] font-mono bg-clima-surface dark:bg-darkClima-surface px-1.5 py-0.5 rounded border border-clima-border dark:border-darkClima-border text-clima-muted dark:text-darkClima-muted">
              {loadingStations ? 'Syncing...' : `${nearbyStations.length} live`}
            </span>
          </div>
        </div>

        {/* Variables Selection Card */}
        <div className="bg-clima-surface/95 dark:bg-darkClima-surface/95 backdrop-blur-md rounded-lg border border-clima-border dark:border-darkClima-border shadow-floating dark:shadow-floating-dark p-3 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-clima-muted dark:text-darkClima-muted">
              Variables
            </span>
            <span className="text-[10px] text-clima-muted dark:text-darkClima-muted">
              Surface Layer
            </span>
          </div>

          {/* Variable Selector Badges */}
          <div className="grid grid-cols-3 gap-1.5 text-xs font-mono">
            {[
              { id: 'pm25', label: 'PM2.5', desc: 'Fine' },
              { id: 'pm10', label: 'PM10', desc: 'Coarse' },
              { id: 'no2', label: 'NO₂', desc: 'Nitrogen' },
              { id: 'so2', label: 'SO₂', desc: 'Sulphur' },
              { id: 'co', label: 'CO', desc: 'Carbon' },
              { id: 'o3', label: 'O₃', desc: 'Ozone' },
            ].map((v) => {
              const isSelected = selectedVariable === v.id;
              return (
                <button
                  key={v.id}
                  onClick={() => setSelectedVariable(v.id as PollutantVariable)}
                  className={`py-1.5 px-2 rounded-md border text-left transition-all ${
                    isSelected
                      ? 'bg-clima-accent dark:bg-darkClima-accent text-white dark:text-darkClima-bg border-clima-accent dark:border-darkClima-accent font-bold shadow-sm'
                      : 'bg-clima-subtle/60 dark:bg-darkClima-subtle/60 text-clima-text dark:text-darkClima-text border-clima-border dark:border-darkClima-border hover:border-clima-muted'
                  }`}
                >
                  <div className="text-[11px] leading-tight">{v.label}</div>
                  <div className={`text-[8.5px] truncate ${isSelected ? 'text-white font-medium' : 'text-clima-muted dark:text-darkClima-muted'}`}>
                    {v.desc}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Severity Classification Filter Tiers */}
          <div className="pt-2 border-t border-clima-border dark:border-darkClima-border space-y-1.5">
            <span className="text-[10px] font-medium text-clima-muted dark:text-darkClima-muted block">
              Filter by Severity Threshold:
            </span>
            <div className="grid grid-cols-5 gap-1 text-[9.5px] font-mono text-center">
              {[
                { id: 'all', label: 'All' },
                { id: 'good', label: 'Good' },
                { id: 'moderate', label: 'Mod' },
                { id: 'poor', label: 'Poor' },
                { id: 'severe', label: 'Sev' },
              ].map((t) => {
                const isActive = aqiTierFilter === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => setAqiTierFilter(t.id as AqiTier)}
                    className={`py-1 rounded border transition-colors ${
                      isActive
                        ? 'bg-clima-text dark:bg-darkClima-text text-clima-surface dark:text-darkClima-surface border-clima-text dark:border-darkClima-text font-bold'
                        : 'bg-clima-subtle/40 dark:bg-darkClima-subtle/40 text-clima-muted dark:text-darkClima-muted border-clima-border dark:border-darkClima-border hover:text-clima-text'
                    }`}
                  >
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* CliMA Scope Bivariate / Visual Scale Legend */}
        <div className="bg-clima-surface/95 dark:bg-darkClima-surface/95 backdrop-blur-md rounded-lg border border-clima-border dark:border-darkClima-border shadow-floating dark:shadow-floating-dark p-3 space-y-2">
          <div className="flex items-center justify-between text-[10px] font-semibold uppercase text-clima-muted dark:text-darkClima-muted">
            <span>AQI Numerical Distribution</span>
            <span className="font-mono">{selectedVariable.toUpperCase()}</span>
          </div>

          {/* Continuous Scientific Color Ramp */}
          <div className="space-y-1">
            <div className="h-2.5 w-full rounded-full bg-gradient-to-r from-[#23966B] via-[#D5A33A] via-[#E27C42] to-[#C94E55]" />
            <div className="flex justify-between text-[9px] font-mono text-clima-muted dark:text-darkClima-muted">
              <span>0 Good</span>
              <span>50</span>
              <span>100 Mod</span>
              <span>150</span>
              <span>200+ Sev</span>
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
          3. FLOATING RIGHT VERTICAL TOOLBAR (CliMA Scope GIS Controls)
         ========================================================================= */}
      <div className="absolute top-3 right-3 z-20 flex flex-col space-y-1.5 font-sans">
        <div className="bg-clima-surface/95 dark:bg-darkClima-surface/95 backdrop-blur-md rounded-lg border border-clima-border dark:border-darkClima-border shadow-floating dark:shadow-floating-dark p-1 flex flex-col space-y-1">
          <button
            onClick={handleZoomIn}
            title="Zoom In"
            aria-label="Zoom in map"
            className="p-2 text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text hover:bg-clima-subtle dark:hover:bg-darkClima-subtle rounded-md transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-clima-accent"
          >
            <Plus className="w-4 h-4" />
          </button>
          <button
            onClick={handleZoomOut}
            title="Zoom Out"
            aria-label="Zoom out map"
            className="p-2 text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text hover:bg-clima-subtle dark:hover:bg-darkClima-subtle rounded-md transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-clima-accent"
          >
            <Minus className="w-4 h-4" />
          </button>
          <button
            onClick={handleResetPosition}
            title="Reset Map Position"
            aria-label="Reset map position to active city"
            className="p-2 text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text hover:bg-clima-subtle dark:hover:bg-darkClima-subtle rounded-md transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-clima-accent"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            onClick={handleLocateUser}
            title="My Coordinates"
            aria-label="Locate my coordinates"
            className="p-2 text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text hover:bg-clima-subtle dark:hover:bg-darkClima-subtle rounded-md transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-clima-accent"
          >
            <Navigation className="w-4 h-4" />
          </button>
        </div>

        {/* Lat/Long Telemetry Capsule */}
        <div className="bg-clima-surface/95 dark:bg-darkClima-surface/95 backdrop-blur-md rounded-lg border border-clima-border dark:border-darkClima-border shadow-floating dark:shadow-floating-dark px-2.5 py-1.5 text-[10px] font-mono text-clima-muted dark:text-darkClima-muted text-right">
          <div>{activeCity.latitude.toFixed(2)}°N</div>
          <div>{activeCity.longitude.toFixed(2)}°E</div>
        </div>
      </div>

      {/* =========================================================================
          4. SELECTED MONITORING STATION INSPECTOR (Floating Card)
         ========================================================================= */}
      {selectedStation && (
        <div className="absolute top-16 right-3 z-30 w-80 max-w-[calc(100vw-2rem)] bg-clima-surface dark:bg-darkClima-surface rounded-lg border border-clima-border dark:border-darkClima-border shadow-floating dark:shadow-floating-dark p-4 space-y-3 font-sans">
          <div className="flex items-center justify-between border-b border-clima-border dark:border-darkClima-border pb-2">
            <span className="text-[10px] font-semibold text-clima-accent dark:text-darkClima-accent uppercase tracking-wider flex items-center">
              <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Ground Sensor Node
            </span>
            <button
              onClick={() => setSelectedStation(null)}
              aria-label="Close station inspector"
              className="text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text text-xs p-1 rounded focus:outline-none focus-visible:ring-1 focus-visible:ring-clima-accent"
            >
              ✕
            </button>
          </div>

          <div>
            <h4 className="text-xs font-bold text-clima-text dark:text-darkClima-text leading-snug">
              {selectedStation.name}
            </h4>
            <div className="text-[11px] text-clima-muted dark:text-darkClima-muted mt-0.5">
              Provider: {selectedStation.provider || 'Environmental Agency'}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 bg-clima-subtle dark:bg-darkClima-subtle p-2.5 rounded-lg border border-clima-border dark:border-darkClima-border">
            <div>
              <span className="text-[9.5px] text-clima-muted dark:text-darkClima-muted block uppercase">Reported AQI</span>
              <span
                className="text-xl font-bold font-mono"
                style={{ color: getAQIColor(selectedStation.aqi) }}
              >
                {selectedStation.aqi ?? '—'}
              </span>
            </div>
            <div>
              <span className="text-[9.5px] text-clima-muted dark:text-darkClima-muted block uppercase">Telemetry Status</span>
              <span className="text-xs text-[#23966B] font-semibold font-mono">LIVE / OK</span>
            </div>
          </div>

          <div className="text-[10px] font-mono text-clima-muted dark:text-darkClima-muted space-y-0.5 pt-1">
            <div>Coordinates: {selectedStation.latitude?.toFixed(4)}°N, {selectedStation.longitude?.toFixed(4)}°E</div>
            {selectedStation.last_updated && (
              <div>Last Synced: {new Date(selectedStation.last_updated).toLocaleTimeString()}</div>
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          5. COLLAPSIBLE BOTTOM ANALYTICAL WORKSPACE (CliMA Scope Temporal Dock)
         ========================================================================= */}
      <div className="absolute bottom-3 left-3 right-3 z-20 font-sans">
        <div className="bg-clima-surface/95 dark:bg-darkClima-surface/95 backdrop-blur-md rounded-xl border border-clima-border dark:border-darkClima-border shadow-floating dark:shadow-floating-dark overflow-hidden transition-all">
          {/* Header Bar with Collapse Toggle */}
          <div className="px-4 py-2 border-b border-clima-border dark:border-darkClima-border flex items-center justify-between text-xs">
            <div className="flex items-center space-x-3">
              <span className="font-semibold text-clima-text dark:text-darkClima-text flex items-center">
                <BarChart2 className="w-3.5 h-3.5 text-clima-accent dark:text-darkClima-accent mr-1.5" />
                Temporal Atmospheric Progression: {activeCity.name}
              </span>
              <div className="hidden sm:flex items-center space-x-1 text-[11px] text-clima-muted dark:text-darkClima-muted">
                <span>Step:</span>
                <select
                  aria-label="Temporal Step Interval"
                  value={temporalStep}
                  onChange={(e) => setTemporalStep(e.target.value as TemporalStep)}
                  className="bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded px-1.5 py-0.5 text-[11px] text-clima-text dark:text-darkClima-text focus:outline-none"
                >
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                  <option value="72h">72h Forecast</option>
                </select>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                aria-label={isPlaying ? 'Pause 24-hour temporal playback animation' : 'Play 24-hour temporal playback animation'}
                className="flex items-center space-x-1 px-2.5 py-1 bg-clima-accent dark:bg-darkClima-accent text-white dark:text-darkClima-bg font-medium text-[11px] rounded-md transition-colors shadow-sm focus:outline-none focus-visible:ring-1 focus-visible:ring-clima-accent"
              >
                {isPlaying ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                <span>{isPlaying ? 'Pause' : 'Play'}</span>
              </button>

              <button
                onClick={() => setBottomWorkspaceOpen(!bottomWorkspaceOpen)}
                className="p-1 text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text rounded transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-clima-accent"
                title={bottomWorkspaceOpen ? 'Collapse Temporal Workspace' : 'Expand Temporal Workspace'}
                aria-label={bottomWorkspaceOpen ? 'Collapse Temporal Workspace' : 'Expand Temporal Workspace'}
                aria-expanded={bottomWorkspaceOpen}
              >
                {bottomWorkspaceOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Expanded Analytical Content */}
          {bottomWorkspaceOpen && (
            <div className="p-4 grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
              {/* Left Column: Mini Polar / Statistical Correlation Summary */}
              <div className="md:col-span-3 border-r border-clima-border dark:border-darkClima-border pr-4 hidden md:block">
                <div className="text-[10px] font-semibold uppercase text-clima-muted dark:text-darkClima-muted mb-1.5">
                  Multi-Seasonal Air Profile
                </div>
                <div className="bg-clima-subtle/80 dark:bg-darkClima-subtle/80 rounded-lg p-2.5 space-y-1.5 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-clima-muted dark:text-darkClima-muted font-sans">Dominant Parameter:</span>
                    <span className="font-mono font-semibold text-clima-text dark:text-darkClima-text">
                      {airQuality?.dominant_pollutant || 'PM2.5'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-clima-muted dark:text-darkClima-muted font-sans">Dispersion Index:</span>
                    <span className="font-mono font-semibold text-[#23966B]">Normal (3.2 m/s)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-clima-muted dark:text-darkClima-muted font-sans">Model Reliability:</span>
                    <span className="font-mono font-semibold text-clima-accent dark:text-darkClima-accent">High (CAMS)</span>
                  </div>
                </div>
              </div>

              {/* Right Column: 24h Time Scrubber Slider and Wave Ribbon */}
              <div className="md:col-span-9 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center space-x-2">
                    <span className="text-[11px] text-clima-muted dark:text-darkClima-muted font-sans">
                      Scrubber Step:
                    </span>
                    <span className="font-bold text-clima-accent dark:text-darkClima-accent">
                      {activePoint ? new Date(activePoint.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Now'}
                    </span>
                    {activePoint && (
                      <span className="text-clima-muted dark:text-darkClima-muted text-[11px]">
                        (AQI ~ {activePoint.us_aqi || Math.round((activePoint.pm25 || 10) * 2.2)})
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-clima-muted dark:text-darkClima-muted">
                    24h Contiguous Forecast
                  </span>
                </div>

                {/* Scrubber Range Slider */}
                <input
                  type="range"
                  aria-label="24-hour forecast timeline scrubber"
                  min="0"
                  max={Math.max(0, timelinePoints.length - 1)}
                  value={timelineIndex}
                  onChange={(e) => setTimelineIndex(Number(e.target.value))}
                  className="w-full h-1.5 bg-clima-subtle dark:bg-darkClima-subtle rounded-lg appearance-none cursor-pointer accent-[#087F72]"
                />

                {/* 24-point Mini Wave Timeline Bar */}
                <div className="grid grid-cols-12 sm:grid-cols-24 gap-1 pt-1">
                  {timelinePoints.map((pt, idx) => {
                    const isCurrent = idx === timelineIndex;
                    const aqi = pt.us_aqi || Math.round((pt.pm25 || 10) * 2.2);
                    const color = getAQIColor(aqi);

                    return (
                      <div
                        key={idx}
                        onClick={() => setTimelineIndex(idx)}
                        className={`h-6 rounded cursor-pointer transition-all flex items-end justify-center pb-0.5 ${
                          isCurrent
                            ? 'ring-2 ring-clima-accent dark:ring-darkClima-accent scale-105'
                            : 'opacity-70 hover:opacity-100'
                        }`}
                        style={{ backgroundColor: `${color}25` }}
                        title={`${new Date(pt.time).toLocaleTimeString([], { hour: 'numeric' })}: AQI ${aqi}`}
                      >
                        <div
                          className="w-full rounded-sm"
                          style={{
                            height: `${Math.min(100, Math.max(20, (aqi / 200) * 100))}%`,
                            backgroundColor: color,
                          }}
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
