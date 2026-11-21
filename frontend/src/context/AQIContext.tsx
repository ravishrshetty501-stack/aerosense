import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { AirQualityResponse, AQIStandard } from '../types/airQuality';
import { api } from '../services/api';

interface CityTarget {
  name: string;
  latitude: number;
  longitude: number;
  country?: string;
}

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

const DEFAULT_CITY: CityTarget = {
  name: "Tokyo",
  country: "Japan",
  latitude: 35.6895,
  longitude: 139.6917
};

const AQIContext = createContext<AQIContextType | undefined>(undefined);

export const AQIProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeCity, setActiveCity] = useState<CityTarget>(DEFAULT_CITY);
  const [standard, setStandard] = useState<AQIStandard>('US_EPA');
  const [airQuality, setAirQuality] = useState<AirQualityResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [popularCities, setPopularCities] = useState<CityTarget[]>([]);

  // Fetch popular cities list on start
  useEffect(() => {
    api.getPopularCities().then(cities => {
      if (cities && cities.length > 0) {
        setPopularCities(cities);
      }
    }).catch(console.error);
  }, []);

  const refreshData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCurrentAirQuality({
        lat: activeCity.latitude,
        lon: activeCity.longitude,
        city: activeCity.name,
        standard: standard,
      });
      setAirQuality(data);
      setLastUpdated(new Date());
    } catch (e: any) {
      console.error('Error fetching air quality:', e);
      setError(e.message || 'Failed to fetch environmental data');
    } finally {
      setLoading(false);
    }
  }, [activeCity, standard]);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  return (
    <AQIContext.Provider
      value={{
        activeCity,
        setActiveCity,
        standard,
        setStandard,
        airQuality,
        loading,
        error,
        lastUpdated,
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
