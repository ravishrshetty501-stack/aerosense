import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { AirQualityResponse, AQIStandard } from '../types/airQuality';
import { api } from '../services/api';

export interface CityTarget {
  name: string;
  latitude: number;
  longitude: number;
  country?: string;
}

export interface AqiRequestState {
  activeCity: CityTarget;
  standard: AQIStandard;
  airQuality: AirQualityResponse | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
}

export type AirQualityFetcher = (
  params: { lat?: number; lon?: number; city?: string; standard?: AQIStandard },
  options?: { signal?: AbortSignal }
) => Promise<AirQualityResponse>;

interface AQIContextType {
  activeCity: CityTarget;
  setActiveCity: (city: CityTarget) => void;
  standard: AQIStandard;
  setStandard: (std: AQIStandard) => void;
  airQuality: AirQualityResponse | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refreshData: () => Promise<void>;
  popularCities: CityTarget[];
}

export const DEFAULT_CITY: CityTarget = {
  name: "Tokyo",
  country: "Japan",
  latitude: 35.6895,
  longitude: 139.6917
};

export function buildCityIdentityKey(city: Pick<CityTarget, 'name' | 'latitude' | 'longitude'>): string {
  const cleanName = typeof city.name === 'string' ? city.name.trim().toLowerCase() : '';
  const latStr = typeof city.latitude === 'number' && Number.isFinite(city.latitude) ? city.latitude.toFixed(4) : 'nan';
  const lonStr = typeof city.longitude === 'number' && Number.isFinite(city.longitude) ? city.longitude.toFixed(4) : 'nan';
  return `${cleanName}|${latStr}|${lonStr}`;
}

export function isAirQualityMatchingCity(
  airQuality: AirQualityResponse | null | undefined,
  city: Pick<CityTarget, 'name' | 'latitude' | 'longitude'>
): boolean {
  if (!airQuality || !airQuality.location) return false;
  const targetName = typeof city.name === 'string' ? city.name.trim().toLowerCase() : '';
  const payloadName = typeof airQuality.location.name === 'string' ? airQuality.location.name.trim().toLowerCase() : '';
  const payloadCity = typeof airQuality.location.city === 'string' ? airQuality.location.city.trim().toLowerCase() : '';
  const nameMatches = Boolean(targetName) && (payloadName === targetName || payloadCity === targetName);
  const coordsMatch =
    typeof airQuality.location.latitude === 'number' &&
    Number.isFinite(airQuality.location.latitude) &&
    typeof airQuality.location.longitude === 'number' &&
    Number.isFinite(airQuality.location.longitude) &&
    Math.abs(airQuality.location.latitude - city.latitude) < 0.05 &&
    Math.abs(airQuality.location.longitude - city.longitude) < 0.05;
  return nameMatches || coordsMatch;
}

/**
 * Coordinates async air-quality fetches with monotonic request-ID + AbortController
 * protection so out-of-order responses never overwrite newer cities and stale city
 * telemetry is never displayed under a new city name after switching or failure.
 */
export function createAqiRequestCoordinator(
  fetcher: AirQualityFetcher,
  initialCity: CityTarget = DEFAULT_CITY,
  initialStandard: AQIStandard = 'US_EPA',
  onStateChange?: (state: AqiRequestState) => void
) {
  let state: AqiRequestState = {
    activeCity: initialCity,
    standard: initialStandard,
    airQuality: null,
    loading: true,
    error: null,
    lastUpdated: null,
  };
  let loadedCityKey: string | null = null;
  let latestRequestId = 0;
  let activeController: AbortController | null = null;

  const emit = (next: Partial<AqiRequestState>) => {
    state = { ...state, ...next };
    onStateChange?.(state);
  };

  const executeFetch = async (city: CityTarget, standard: AQIStandard): Promise<AqiRequestState> => {
    const hasValidCity =
      typeof city?.name === 'string' &&
      city.name.trim().length > 0 &&
      typeof city.latitude === 'number' &&
      Number.isFinite(city.latitude) &&
      typeof city.longitude === 'number' &&
      Number.isFinite(city.longitude);

    if (activeController) {
      activeController.abort();
      activeController = null;
    }

    const requestId = ++latestRequestId;

    if (!hasValidCity) {
      loadedCityKey = null;
      emit({
        activeCity: city,
        standard,
        airQuality: null,
        loading: false,
        error: 'Selected location has invalid coordinates.',
      });
      return state;
    }

    const targetKey = buildCityIdentityKey(city);
    const sameLoadedCity =
      loadedCityKey === targetKey && isAirQualityMatchingCity(state.airQuality, city);

    const controller = new AbortController();
    activeController = controller;

    emit({
      activeCity: city,
      standard,
      airQuality: sameLoadedCity ? state.airQuality : null,
      loading: true,
      error: null,
    });
    if (!sameLoadedCity) {
      loadedCityKey = null;
    }

    try {
      const data = await fetcher(
        {
          lat: city.latitude,
          lon: city.longitude,
          city: city.name,
          standard,
        },
        { signal: controller.signal }
      );

      if (requestId !== latestRequestId || controller.signal.aborted) {
        return state;
      }

      if (!data || typeof data !== 'object') {
        throw new Error('Received empty atmospheric response.');
      }

      loadedCityKey = targetKey;
      emit({
        activeCity: city,
        standard,
        airQuality: data,
        loading: false,
        error: null,
        lastUpdated: new Date(),
      });
    } catch (e: unknown) {
      if (controller.signal.aborted || (e instanceof Error && e.name === 'AbortError')) {
        if (requestId === latestRequestId) {
          emit({ loading: false });
        }
        return state;
      }
      if (requestId !== latestRequestId) {
        return state;
      }
      const errMsg =
        e instanceof Error
          ? e.message
          : typeof e === 'string'
          ? e
          : 'Failed to fetch environmental data';

      const keepMatchingData =
        loadedCityKey === targetKey && isAirQualityMatchingCity(state.airQuality, city);
      if (!keepMatchingData) {
        loadedCityKey = null;
      }
      emit({
        activeCity: city,
        standard,
        airQuality: keepMatchingData ? state.airQuality : null,
        loading: false,
        error: errMsg,
      });
    } finally {
      if (activeController === controller) {
        activeController = null;
      }
      if (requestId === latestRequestId && state.loading) {
        emit({ loading: false });
      }
    }

    return state;
  };

  return {
    getState: (): AqiRequestState => state,
    fetchForTarget: executeFetch,
    cancelActive: () => {
      latestRequestId += 1;
      if (activeController) {
        activeController.abort();
        activeController = null;
      }
      if (state.loading) {
        emit({ loading: false });
      }
    },
  };
}

const AQIContext = createContext<AQIContextType | undefined>(undefined);

export const AQIProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeCity, setActiveCity] = useState<CityTarget>(DEFAULT_CITY);
  const [standard, setStandard] = useState<AQIStandard>('US_EPA');
  const [requestState, setRequestState] = useState<AqiRequestState>({
    activeCity: DEFAULT_CITY,
    standard: 'US_EPA',
    airQuality: null,
    loading: true,
    error: null,
    lastUpdated: null,
  });
  const [popularCities, setPopularCities] = useState<CityTarget[]>([]);

  const coordinatorRef = useRef<ReturnType<typeof createAqiRequestCoordinator> | null>(null);
  if (!coordinatorRef.current) {
    coordinatorRef.current = createAqiRequestCoordinator(
      (params, options) => api.getCurrentAirQuality(params, options),
      DEFAULT_CITY,
      'US_EPA',
      (nextState) => setRequestState(nextState)
    );
  }

  // Fetch popular cities list on start
  useEffect(() => {
    let active = true;
    api.getPopularCities().then(cities => {
      if (active && cities && cities.length > 0) {
        setPopularCities(cities);
      }
    }).catch(console.error);
    return () => {
      active = false;
    };
  }, []);

  const refreshData = useCallback(async () => {
    await coordinatorRef.current?.fetchForTarget(activeCity, standard);
  }, [activeCity, standard]);

  useEffect(() => {
    refreshData();
    return () => {
      coordinatorRef.current?.cancelActive();
    };
  }, [refreshData]);

  return (
    <AQIContext.Provider
      value={{
        activeCity,
        setActiveCity,
        standard,
        setStandard,
        airQuality: requestState.airQuality,
        loading: requestState.loading,
        error: requestState.error,
        lastUpdated: requestState.lastUpdated,
        refreshData,
        popularCities,
      }}
    >
      {children}
    </AQIContext.Provider>
  );
};

export const useAQI = () => {
  const ctx = useContext(AQIContext);
  if (!ctx) throw new Error('useAQI must be used within an AQIProvider');
  return ctx;
};
