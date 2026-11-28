import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { useAQI } from '../../context/AQIContext';
import { useTheme } from '../../context/ThemeContext';
import { api } from '../../services/api';
import { AirQualityResponse, HourlyTrendPoint, MonitoringStation, NormalizedMeasurement } from '../../types/airQuality';
import { getAqiScaleColor, resolveForecastAqi } from '../../utils/airQualityHelpers';
import {
  Radio,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  Navigation,
  Play,
  Pause,
  BarChart2,
  Plus,
  Minus,
  RotateCcw,
} from 'lucide-react';

export type AqiTier = 'all' | 'good' | 'moderate' | 'poor' | 'severe';
export type TemporalStep = 'hourly' | 'daily' | '72h';

/**
 * Filters monitoring stations by AQI severity tier without fabricating a fallback for null/missing AQI.
 */
export function filterStationsByAqiTier(stations: MonitoringStation[], tier: AqiTier): MonitoringStation[] {
  if (tier === 'all') return stations;
  return stations.filter((st) => {
    const val = st.aqi;
    if (typeof val !== 'number' || !Number.isFinite(val)) {
      return false;
    }
    if (tier === 'good') return val <= 50;
    if (tier === 'moderate') return val > 50 && val <= 100;
    if (tier === 'poor') return val > 100 && val <= 150;
    if (tier === 'severe') return val > 150;
    return true;
  });
}

const ONE_HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * ONE_HOUR_MS;

function parseTimestampMs(timeStr: unknown): number | null {
  if (typeof timeStr !== 'string' || !timeStr.trim()) return null;
  const ms = Date.parse(timeStr);
  return Number.isFinite(ms) ? ms : null;
}

function isValidMeasurementValue(val: unknown): val is number {
  return typeof val === 'number' && Number.isFinite(val);
}

interface ParsedForecastEntry {
  pt: HourlyTrendPoint;
  ms: number;
  origIdx: number;
  resolvedAqi: number | null;
}

/**
 * Selects timeline points from real forecast series after chronological sorting and timestamp deduplication,
 * producing labels that accurately reflect observation counts and elapsed timestamp spans.
 */
export function selectTemporalTimelinePoints(
  forecast: HourlyTrendPoint[] | null | undefined,
  step: TemporalStep
): { points: HourlyTrendPoint[]; label: string } {
  const safeForecast = Array.isArray(forecast) ? forecast : [];
  if (safeForecast.length === 0) {
    return {
      points: [],
      label: step === 'daily' ? 'Daily Snapshots Unavailable' : 'Forecast Unavailable',
    };
  }

  const parsedEntries: ParsedForecastEntry[] = [];
  safeForecast.forEach((pt, origIdx) => {
    const ms = parseTimestampMs(pt?.time);
    if (ms !== null) {
      parsedEntries.push({
        pt,
        ms,
        origIdx,
        resolvedAqi: resolveForecastAqi(pt),
      });
    }
  });

  if (parsedEntries.length === 0) {
    const fallbackPoints = safeForecast.slice(0, 24);
    const validCount = fallbackPoints.filter((pt) => resolveForecastAqi(pt) !== null).length;
    return {
      points: fallbackPoints,
      label:
        validCount === 0
          ? step === 'daily'
            ? 'Daily Snapshots Unavailable'
            : 'Forecast Unavailable'
          : `${step === 'daily' ? 'Daily Snapshots' : 'Forecast'} (${validCount} valid pts, unverified timestamps)`,
    };
  }

  // Sort chronologically while preserving original relative order on equal timestamps
  parsedEntries.sort((a, b) => (a.ms !== b.ms ? a.ms - b.ms : a.origIdx - b.origIdx));

  // Deduplicate equal timestamps: prefer first valid AQI entry; otherwise retain one unavailable entry
  const dedupedByTimestamp = new Map<number, ParsedForecastEntry>();
  for (const entry of parsedEntries) {
    const existing = dedupedByTimestamp.get(entry.ms);
    if (!existing) {
      dedupedByTimestamp.set(entry.ms, entry);
    } else if (existing.resolvedAqi === null && entry.resolvedAqi !== null) {
      dedupedByTimestamp.set(entry.ms, entry);
    }
  }
  const deduped = Array.from(dedupedByTimestamp.values());
  const t0 = deduped[0].ms;

  if (step === 'daily') {
    const selected: ParsedForecastEntry[] = [];
    const seenBuckets = new Set<number>();
    for (const item of deduped) {
      if (item.ms - t0 > 72 * ONE_HOUR_MS) break;
      const dayBucket = Math.floor((item.ms - t0) / DAY_MS);
      if (dayBucket >= 3) break;
      if (!seenBuckets.has(dayBucket)) {
        seenBuckets.add(dayBucket);
        selected.push(item);
      }
    }
    const points = selected.map((s) => s.pt);
    const validSelected = selected.filter((s) => s.resolvedAqi !== null);
    if (validSelected.length === 0) {
      return { points, label: 'Daily Snapshots Unavailable' };
    }
    if (validSelected.length === 1) {
      return { points, label: 'Daily Forecast Snapshot (Single point)' };
    }
    const spanHours = Math.round((validSelected[validSelected.length - 1].ms - validSelected[0].ms) / ONE_HOUR_MS);
    const countLabel =
      validSelected.length < points.length
        ? `${validSelected.length} of ${points.length} valid`
        : `${validSelected.length} pts`;
    return {
      points,
      label: `Daily Forecast Snapshots (${countLabel}, ${spanHours}h span)`,
    };
  }

  if (step === '72h') {
    const selected: ParsedForecastEntry[] = [];
    for (const item of deduped) {
      if (item.ms - t0 > 72 * ONE_HOUR_MS) break;
      if (selected.length === 0 || item.ms - selected[selected.length - 1].ms >= 3 * ONE_HOUR_MS) {
        selected.push(item);
        if (selected.length === 24) break;
      }
    }
    const points = selected.map((s) => s.pt);
    const validSelected = selected.filter((s) => s.resolvedAqi !== null);
    if (validSelected.length === 0) {
      return { points, label: 'Forecast Unavailable' };
    }
    if (validSelected.length === 1) {
      return { points, label: 'Forecast Snapshot (Single point)' };
    }
    const spanHours = Math.round((validSelected[validSelected.length - 1].ms - validSelected[0].ms) / ONE_HOUR_MS);
    const allPointsValid = validSelected.length === selected.length;
    const isUniform3hStep =
      allPointsValid &&
      selected.every((item, idx) => idx === 0 || item.ms - selected[idx - 1].ms === 3 * ONE_HOUR_MS);
    const cadenceLabel = isUniform3hStep ? '3h Step' : 'Irregular / Partial Step';
    return {
      points,
      label: `${spanHours}h Forecast Trajectory (${cadenceLabel})`,
    };
  }

  // step === 'hourly'
  const selected = deduped
    .filter((item) => item.ms - t0 <= 23 * ONE_HOUR_MS)
    .slice(0, 24);
  const points = selected.map((s) => s.pt);
  const validSelected = selected.filter((s) => s.resolvedAqi !== null);

  if (validSelected.length === 0) {
    return { points, label: 'Forecast Unavailable' };
  }
  const allPointsValid = validSelected.length === selected.length;
  const isContiguousHourly =
    allPointsValid &&
    selected.every((item, idx) => idx === 0 || item.ms - selected[idx - 1].ms === ONE_HOUR_MS);

  if (isContiguousHourly) {
    if (selected.length === 1) {
      return { points, label: 'Hourly Forecast Snapshot (1 pt)' };
    }
    const spanHours = Math.round((selected[selected.length - 1].ms - selected[0].ms) / ONE_HOUR_MS);
    return {
      points,
      label: `Hourly Forecast (${selected.length} pts, ${spanHours}h span)`,
    };
  }
  if (validSelected.length === 1) {
    return { points, label: 'Hourly Forecast (1 valid pt, gaps detected)' };
  }
  const validSpanHours = Math.round(
    (validSelected[validSelected.length - 1].ms - validSelected[0].ms) / ONE_HOUR_MS
  );
  return {
    points,
    label: `Hourly Forecast (${validSelected.length} valid pts, ${validSpanHours}h span, gaps detected)`,
  };
}

/**
 * Derives verified telemetry status metrics without fabricating unavailable model estimates or active streams.
 */
export function buildMapTelemetrySummary(airQuality: AirQualityResponse | null): {
  dominantPollutant: string;
  observationMode: string;
  forecastStatus: string;
} {
  if (!airQuality) {
    return {
      dominantPollutant: 'Unavailable',
      observationMode: 'Unavailable',
      forecastStatus: 'Unavailable',
    };
  }

  const validMeasurements = Object.values(airQuality.measurements || {}).filter(
    (m): m is NormalizedMeasurement => Boolean(m) && isValidMeasurementValue(m.value)
  );
  const hasGroundMeasurement = validMeasurements.some(
    (m) => m.measurement_type === 'ground_observation'
  );
  const hasModelMeasurement = validMeasurements.some(
    (m) => m.measurement_type === 'model_estimate'
  );

  let observationMode = 'Unavailable';
  if (hasGroundMeasurement) {
    observationMode = 'Ground Sensor';
  } else if (hasModelMeasurement) {
    observationMode = 'Model Estimate';
  }

  const hasValidForecast =
    Array.isArray(airQuality.forecast) &&
    airQuality.forecast.some(
      (pt) =>
        resolveForecastAqi(pt) !== null ||
        isValidMeasurementValue(pt?.pm25) ||
        isValidMeasurementValue(pt?.pm10) ||
        isValidMeasurementValue(pt?.no2) ||
        isValidMeasurementValue(pt?.o3)
    );

  return {
    dominantPollutant: airQuality.dominant_pollutant || 'Unavailable',
    observationMode,
    forecastStatus: hasValidForecast ? 'Active' : 'Unavailable',
  };
}

/**
 * Safely constructs the geographical focus popup DOM element without HTML interpolation,
 * using theme CSS variables so text remains readable in both light and dark modes.
 */
export function buildCityPopupElement(
  cityName: string,
  latitude: number,
  longitude: number,
  doc: Document = document
): HTMLElement {
  const container = doc.createElement('div');
  container.style.fontSize = '11px';

  const titleEl = doc.createElement('div');
  titleEl.style.color = 'var(--accent-primary, #087F73)';
  titleEl.style.fontWeight = '700';
  titleEl.textContent = cityName;

  const subtitleEl = doc.createElement('div');
  subtitleEl.style.color = 'var(--text-secondary, #687771)';
  subtitleEl.style.fontSize = '10px';
  subtitleEl.textContent = 'Geographical Focus Location';

  const coordsEl = doc.createElement('div');
  coordsEl.style.color = 'var(--text-primary, #172522)';
  coordsEl.style.fontFamily = 'monospace';
  coordsEl.style.fontSize = '10px';
  coordsEl.style.marginTop = '3px';
  coordsEl.textContent = `${latitude.toFixed(4)}°N, ${longitude.toFixed(4)}°E`;

  container.appendChild(titleEl);
  container.appendChild(subtitleEl);
  container.appendChild(coordsEl);
  return container;
}

/**
 * Safely constructs a monitoring station popup DOM element without HTML interpolation,
 * using theme CSS variables for light and dark theme readability.
 */
export function buildStationPopupElement(
  station: Pick<MonitoringStation, 'name' | 'aqi' | 'provider'>,
  color: string,
  doc: Document = document
): HTMLElement {
  const container = doc.createElement('div');
  container.style.fontSize = '11px';
  container.style.maxWidth = '200px';

  const headerEl = doc.createElement('div');
  headerEl.style.display = 'flex';
  headerEl.style.alignItems = 'center';
  headerEl.style.justifyContent = 'space-between';
  headerEl.style.marginBottom = '2px';

  const hasValidAqi = typeof station.aqi === 'number' && Number.isFinite(station.aqi);
  const aqiEl = doc.createElement('span');
  aqiEl.style.color = color;
  aqiEl.style.fontWeight = '700';
  aqiEl.style.fontFamily = 'monospace';
  aqiEl.textContent = hasValidAqi ? `AQI ${station.aqi}` : 'AQI N/A';

  const kindEl = doc.createElement('span');
  kindEl.style.fontSize = '9px';
  kindEl.style.color = 'var(--text-secondary, #687771)';
  kindEl.textContent = 'Ground Station';

  headerEl.appendChild(aqiEl);
  headerEl.appendChild(kindEl);

  const nameEl = doc.createElement('div');
  nameEl.style.fontWeight = '600';
  nameEl.style.color = 'var(--text-primary, #172522)';
  nameEl.style.lineHeight = '1.3';
  nameEl.textContent = station.name;

  const providerEl = doc.createElement('div');
  providerEl.style.fontSize = '9.5px';
  providerEl.style.color = 'var(--text-secondary, #687771)';
  providerEl.style.marginTop = '4px';
  providerEl.textContent = `Provider: ${station.provider || 'Regional Agency'}`;

  container.appendChild(headerEl);
  container.appendChild(nameEl);
  container.appendChild(providerEl);
  return container;
}

export const GlobalPollutionMap: React.FC = () => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const { activeCity, airQuality } = useAQI();
  const { resolvedTheme } = useTheme();

  // Control panel states
  const [selectedStation, setSelectedStation] = useState<MonitoringStation | null>(null);
  const [nearbyStations, setNearbyStations] = useState<MonitoringStation[]>([]);
  const [loadingStations, setLoadingStations] = useState<boolean>(false);
  const [aqiTierFilter, setAqiTierFilter] = useState<AqiTier>('all');
  const [bottomWorkspaceOpen, setBottomWorkspaceOpen] = useState<boolean>(true);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [timelineIndex, setTimelineIndex] = useState<number>(0);
  const [temporalStep, setTemporalStep] = useState<TemporalStep>('hourly');

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

  // Forecast points for bottom timeline scrubber
  const { points: timelinePoints, label: timelineWindowLabel } = selectTemporalTimelinePoints(
    airQuality?.forecast,
    temporalStep
  );
  const telemetrySummary = buildMapTelemetrySummary(airQuality);

  // Pan to active city when changed & fetch stations
  useEffect(() => {
    if (!map.current) return;
    map.current.flyTo({
      center: [activeCity.longitude, activeCity.latitude],
      zoom: 10,
      essential: true,
      duration: 1200,
    });

    let active = true;
    setLoadingStations(true);
    setSelectedStation(null);
    setNearbyStations([]);
    api.getNearbyStations(activeCity.latitude, activeCity.longitude)
      .then((stations) => {
        if (active) setNearbyStations(stations);
      })
      .catch((err) => {
        console.error(err);
        if (active) setNearbyStations([]);
      })
      .finally(() => {
        if (active) setLoadingStations(false);
      });

    return () => {
      active = false;
    };
  }, [activeCity]);

  // Reset timeline index when temporal step or city changes
  useEffect(() => {
    setTimelineIndex(0);
    setIsPlaying(false);
  }, [temporalStep, activeCity]);

  // Time scrubber autoplay
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    if (isPlaying && timelinePoints.length > 0) {
      interval = setInterval(() => {
        setTimelineIndex((prev) => (prev + 1) % timelinePoints.length);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isPlaying, timelinePoints.length]);

  // Filter stations based on AQI severity selection without coercing null to 50
  const filteredStations = filterStationsByAqiTier(nearbyStations, aqiTierFilter);

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
        new maplibregl.Popup({ offset: 12 }).setDOMContent(
          buildCityPopupElement(activeCity.name, activeCity.latitude, activeCity.longitude)
        )
      )
      .addTo(map.current!);

    markers.push(cityMarker);

    // 2. Physical Monitoring Station Pins
    filteredStations.forEach((st) => {
      if (
        typeof st.latitude !== 'number' ||
        !Number.isFinite(st.latitude) ||
        typeof st.longitude !== 'number' ||
        !Number.isFinite(st.longitude)
      ) {
        return;
      }

      const color = getAqiScaleColor(st.aqi, '#159DB0');
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
      const hasPinAqi = typeof st.aqi === 'number' && Number.isFinite(st.aqi);
      stEl.innerText = hasPinAqi ? String(st.aqi) : '●';

      stEl.addEventListener('click', () => {
        setSelectedStation(st);
      });

      const stMarker = new maplibregl.Marker(stEl)
        .setLngLat([st.longitude, st.latitude])
        .setPopup(
          new maplibregl.Popup({ offset: 14 }).setDOMContent(
            buildStationPopupElement(st, color)
          )
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

  const safeIndex = Math.min(timelineIndex, Math.max(0, timelinePoints.length - 1));
  const activePoint = timelinePoints[safeIndex] || null;
  const activePointAqi = activePoint ? resolveForecastAqi(activePoint) : null;

  return (
    <div className="relative w-full h-[calc(100vh-3.5rem)] bg-clima-bg dark:bg-darkClima-bg overflow-hidden select-none">
      {/* MapLibre WebGL Canvas */}
      <div ref={mapContainer} className="w-full h-full" />

      {/* =========================================================================
          1. FLOATING LEFT CONTROL DOCK (Monitoring Array & Severity Filters)
         ========================================================================= */}
      <div className="absolute top-3 left-3 z-20 w-72 max-w-[calc(100vw-1.5rem)] space-y-2 font-sans">
        {/* Datasets Summary Card */}
        <div className="bg-clima-surface/95 dark:bg-darkClima-surface/95 backdrop-blur-md rounded-lg border border-clima-border dark:border-darkClima-border shadow-floating dark:shadow-floating-dark p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-clima-muted dark:text-darkClima-muted">
              Sensor Network
            </span>
            <span className="text-[10px] font-mono text-clima-accent dark:text-darkClima-accent font-medium">
              {filteredStations.length} shown
            </span>
          </div>

          <div className="bg-clima-subtle/80 dark:bg-darkClima-subtle/80 rounded-md p-2 flex items-center justify-between text-xs">
            <div className="flex items-center space-x-2">
              <Radio className="w-3.5 h-3.5 text-clima-accent dark:text-darkClima-accent animate-pulse" />
              <span className="font-medium text-clima-text dark:text-darkClima-text">
                {nearbyStations[0]?.provider?.includes('OpenAQ') ? 'OpenAQ Sensor Array' : 'Ground Sensor Array'}
              </span>
            </div>
            <span className="text-[10px] font-mono bg-clima-surface dark:bg-darkClima-surface px-1.5 py-0.5 rounded border border-clima-border dark:border-darkClima-border text-clima-muted dark:text-darkClima-muted">
              {loadingStations ? 'Syncing...' : `${nearbyStations.length} live`}
            </span>
          </div>
        </div>

        {/* Severity Classification Filter Tiers */}
        <div className="bg-clima-surface/95 dark:bg-darkClima-surface/95 backdrop-blur-md rounded-lg border border-clima-border dark:border-darkClima-border shadow-floating dark:shadow-floating-dark p-3 space-y-1.5">
          <span className="text-[10px] font-medium text-clima-muted dark:text-darkClima-muted block">
            Filter Stations by AQI Severity:
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

        {/* AQI Numerical Visual Scale Legend */}
        <div className="bg-clima-surface/95 dark:bg-darkClima-surface/95 backdrop-blur-md rounded-lg border border-clima-border dark:border-darkClima-border shadow-floating dark:shadow-floating-dark p-3 space-y-2">
          <div className="flex items-center justify-between text-[10px] font-semibold uppercase text-clima-muted dark:text-darkClima-muted">
            <span>Station AQI Distribution</span>
            <span className="font-mono">US EPA</span>
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
                style={{ color: getAqiScaleColor(selectedStation.aqi, '#159DB0') }}
              >
                {typeof selectedStation.aqi === 'number' && Number.isFinite(selectedStation.aqi)
                  ? selectedStation.aqi
                  : '—'}
              </span>
            </div>
            <div>
              <span className="text-[9.5px] text-clima-muted dark:text-darkClima-muted block uppercase">Telemetry Status</span>
              <span
                className={`text-xs font-semibold font-mono ${
                  typeof selectedStation.aqi === 'number' && Number.isFinite(selectedStation.aqi)
                    ? 'text-[#23966B]'
                    : 'text-clima-muted dark:text-darkClima-muted'
                }`}
              >
                {typeof selectedStation.aqi === 'number' && Number.isFinite(selectedStation.aqi)
                  ? 'LIVE / OK'
                  : 'ACTIVE (AQI N/A)'}
              </span>
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
              {/* Left Column: Verified Telemetry Status Summary */}
              <div className="md:col-span-3 border-r border-clima-border dark:border-darkClima-border pr-4 hidden md:block">
                <div className="text-[10px] font-semibold uppercase text-clima-muted dark:text-darkClima-muted mb-1.5">
                  Station Atmospheric Summary
                </div>
                <div className="bg-clima-subtle/80 dark:bg-darkClima-subtle/80 rounded-lg p-2.5 space-y-1.5 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-clima-muted dark:text-darkClima-muted font-sans">Dominant Parameter:</span>
                    <span className="font-mono font-semibold text-clima-text dark:text-darkClima-text">
                      {telemetrySummary.dominantPollutant}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-clima-muted dark:text-darkClima-muted font-sans">Source Mode:</span>
                    <span className="font-mono font-semibold text-clima-text dark:text-darkClima-text">
                      {telemetrySummary.observationMode}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-clima-muted dark:text-darkClima-muted font-sans">Forecast Stream:</span>
                    <span
                      className={`font-mono font-semibold ${
                        telemetrySummary.forecastStatus === 'Active'
                          ? 'text-clima-accent dark:text-darkClima-accent'
                          : 'text-clima-muted dark:text-darkClima-muted'
                      }`}
                    >
                      {telemetrySummary.forecastStatus}
                    </span>
                  </div>
                </div>
              </div>

              {/* Right Column: Time Scrubber Slider and Wave Ribbon */}
              <div className="md:col-span-9 space-y-2">
                <div className="flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center space-x-2">
                    <span className="text-[11px] text-clima-muted dark:text-darkClima-muted font-sans">
                      Scrubber Step:
                    </span>
                    <span className="font-bold text-clima-accent dark:text-darkClima-accent">
                      {activePoint
                        ? (() => {
                            const d = new Date(activePoint.time);
                            return Number.isNaN(d.getTime())
                              ? activePoint.time
                              : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                          })()
                        : 'Now'}
                    </span>
                    {activePoint && (
                      <span className="text-clima-muted dark:text-darkClima-muted text-[11px]">
                        {activePointAqi !== null ? `(AQI ~ ${activePointAqi})` : '(AQI N/A)'}
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-clima-muted dark:text-darkClima-muted">
                    {timelineWindowLabel}
                  </span>
                </div>

                {/* Scrubber Range Slider */}
                <input
                  type="range"
                  aria-label="Forecast timeline scrubber"
                  min="0"
                  max={Math.max(0, timelinePoints.length - 1)}
                  value={safeIndex}
                  onChange={(e) => setTimelineIndex(Number(e.target.value))}
                  className="w-full h-1.5 bg-clima-subtle dark:bg-darkClima-subtle rounded-lg appearance-none cursor-pointer accent-[#087F72]"
                />

                {/* Mini Wave Timeline Bar */}
                <div
                  className={`grid gap-1 pt-1 ${
                    temporalStep === 'daily' ? 'grid-cols-3' : 'grid-cols-12 sm:grid-cols-24'
                  }`}
                >
                  {timelinePoints.map((pt, idx) => {
                    const isCurrent = idx === safeIndex;
                    const aqi = resolveForecastAqi(pt);
                    const color = getAqiScaleColor(aqi, '#159DB0');

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
                        title={`${new Date(pt.time).toLocaleTimeString([], { hour: 'numeric' })}: AQI ${aqi !== null ? aqi : 'N/A'}`}
                      >
                        <div
                          className="w-full rounded-sm"
                          style={{
                            height: `${aqi !== null ? Math.min(100, Math.max(20, (aqi / 200) * 100)) : 0}%`,
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
