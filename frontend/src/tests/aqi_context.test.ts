import { describe, it, expect, vi } from 'vitest';
import {
  AirQualityFetcher,
  CityTarget,
  createAqiRequestCoordinator,
  isAirQualityMatchingCity,
} from '../context/AQIContext';
import { api } from '../services/api';
import { AirQualityResponse } from '../types/airQuality';

function makeCity(name: string, lat: number, lon: number): CityTarget {
  return { name, latitude: lat, longitude: lon };
}

function makeAqPayload(city: CityTarget, aqi: number): AirQualityResponse {
  return {
    location: {
      name: city.name,
      city: city.name,
      latitude: city.latitude,
      longitude: city.longitude,
      timezone: 'UTC',
    },
    measurements: {
      pm25: {
        pollutant: 'pm25',
        value: aqi,
        unit: 'µg/m³',
        measurement_type: 'ground_observation',
        source: `${city.name} Station`,
        data_quality: 'verified',
        observation_timestamp: '2026-11-27T10:00:00Z',
        retrieval_timestamp: '2026-11-27T10:05:00Z',
      },
    },
    aqi_standard_results: {
      US_EPA: {
        standard: 'US_EPA',
        aqi,
        category: 'Good',
        dominant_pollutant: 'PM25',
        color: '#23966B',
        subindices: { pm25: aqi },
        advisory: 'Clean air.',
        is_reliable: true,
      },
    },
    dominant_pollutant: 'PM25',
    hourly_history: [],
    forecast: [],
    primary_source: `${city.name} Source`,
    data_freshness_minutes: 5,
    is_ground_observation: true,
  };
}

function createDeferred<T>() {
  let resolve!: (val: T) => void;
  let reject!: (err: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('Phase D.3.3: AQIContext stale city request protection & error recovery', () => {
  const cityA = makeCity('Tokyo', 35.6895, 139.6917);
  const cityB = makeCity('Delhi', 28.6139, 77.2090);

  it('clears City A telemetry when switching to City B and keeps error visible when City B fails', async () => {
    const fetcher = vi.fn<AirQualityFetcher>()
      .mockResolvedValueOnce(makeAqPayload(cityA, 25))
      .mockRejectedValueOnce(new Error('Upstream station timeout for Delhi'));

    const coordinator = createAqiRequestCoordinator(fetcher, cityA, 'US_EPA');

    // 1. City A loads successfully
    const stateAfterA = await coordinator.fetchForTarget(cityA, 'US_EPA');
    expect(stateAfterA.loading).toBe(false);
    expect(stateAfterA.error).toBeNull();
    expect(stateAfterA.airQuality?.location.name).toBe('Tokyo');
    expect(stateAfterA.airQuality?.aqi_standard_results.US_EPA.aqi).toBe(25);

    // 2-4. Switch to City B and fail -> City A data must NOT remain shown under City B
    const stateAfterB = await coordinator.fetchForTarget(cityB, 'US_EPA');
    expect(stateAfterB.activeCity.name).toBe('Delhi');
    expect(stateAfterB.loading).toBe(false);
    expect(stateAfterB.airQuality).toBeNull();
    expect(stateAfterB.error).toBe('Upstream station timeout for Delhi');
  });

  it('prevents an older slow City A response or rejection from overwriting newer City B state', async () => {
    const deferredA = createDeferred<AirQualityResponse>();
    const deferredB = createDeferred<AirQualityResponse>();

    const signals: Array<AbortSignal | undefined> = [];
    const fetcher = vi.fn<AirQualityFetcher>().mockImplementation((params, options) => {
      signals.push(options?.signal);
      if (params.city === 'Tokyo') return deferredA.promise;
      return deferredB.promise;
    });

    const coordinator = createAqiRequestCoordinator(fetcher, cityA, 'US_EPA');

    // Start slow City A request, then immediately switch to City B
    const promiseA = coordinator.fetchForTarget(cityA, 'US_EPA');
    const promiseB = coordinator.fetchForTarget(cityB, 'US_EPA');

    // Previous request's AbortSignal must have been aborted
    expect(signals[0]?.aborted).toBe(true);
    expect(signals[1]?.aborted).toBe(false);

    // City B finishes first
    deferredB.resolve(makeAqPayload(cityB, 180));
    await promiseB;

    expect(coordinator.getState().loading).toBe(false);
    expect(coordinator.getState().airQuality?.location.name).toBe('Delhi');
    expect(coordinator.getState().airQuality?.aqi_standard_results.US_EPA.aqi).toBe(180);

    // Older City A resolves AFTER City B (even if caller ignores signal) -> must NOT overwrite City B
    deferredA.resolve(makeAqPayload(cityA, 15));
    await promiseA;

    const finalState = coordinator.getState();
    expect(finalState.activeCity.name).toBe('Delhi');
    expect(finalState.airQuality?.location.name).toBe('Delhi');
    expect(finalState.airQuality?.aqi_standard_results.US_EPA.aqi).toBe(180);
    expect(finalState.error).toBeNull();
    expect(finalState.loading).toBe(false);

    // Now test older rejection arriving after a newer request succeeds
    const slowReject = createDeferred<AirQualityResponse>();
    const fastOk = createDeferred<AirQualityResponse>();
    const raceFetcher = vi.fn<AirQualityFetcher>()
      .mockImplementationOnce(() => slowReject.promise)
      .mockImplementationOnce(() => fastOk.promise);

    const raceCoord = createAqiRequestCoordinator(raceFetcher, cityA, 'US_EPA');
    const p1 = raceCoord.fetchForTarget(cityA, 'US_EPA');
    const p2 = raceCoord.fetchForTarget(cityB, 'US_EPA');

    fastOk.resolve(makeAqPayload(cityB, 140));
    await p2;
    slowReject.reject(new Error('Stale network failure'));
    await p1;

    expect(raceCoord.getState().airQuality?.location.name).toBe('Delhi');
    expect(raceCoord.getState().error).toBeNull();
    expect(raceCoord.getState().loading).toBe(false);
  });

  it('preserves matching same-city data while exposing error on failed refresh and resets loading on early return', async () => {
    const fetcher = vi.fn<AirQualityFetcher>()
      .mockResolvedValueOnce(makeAqPayload(cityB, 160))
      .mockRejectedValueOnce(new Error('Temporary refresh failure'));

    const coordinator = createAqiRequestCoordinator(fetcher, cityB, 'US_EPA');
    await coordinator.fetchForTarget(cityB, 'US_EPA');

    const refreshed = await coordinator.fetchForTarget(cityB, 'US_EPA');
    expect(refreshed.loading).toBe(false);
    expect(refreshed.error).toBe('Temporary refresh failure');
    expect(refreshed.airQuality?.location.name).toBe('Delhi');
    expect(isAirQualityMatchingCity(refreshed.airQuality, cityB)).toBe(true);

    // Invalid coordinates early return resets loading without calling fetcher
    const badCity = makeCity('InvalidCity', Number.NaN, 0);
    const badState = await coordinator.fetchForTarget(badCity, 'US_EPA');
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(badState.loading).toBe(false);
    expect(badState.airQuality).toBeNull();
    expect(badState.error).toBeTruthy();

    // Cancel active fetch cleanly resets loading
    const hanging = createDeferred<AirQualityResponse>();
    const hangCoord = createAqiRequestCoordinator(() => hanging.promise, cityA, 'US_EPA');
    const hangPromise = hangCoord.fetchForTarget(cityA, 'US_EPA');
    expect(hangCoord.getState().loading).toBe(true);
    hangCoord.cancelActive();
    expect(hangCoord.getState().loading).toBe(false);
    hanging.resolve(makeAqPayload(cityA, 10));
    await hangPromise;
    expect(hangCoord.getState().airQuality).toBeNull();
  });

  it('forwards optional AbortSignal from api.getCurrentAirQuality to fetch', async () => {
    let capturedInit: RequestInit | undefined;
    global.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      capturedInit = init;
      return Promise.resolve({
        ok: true,
        json: async () => makeAqPayload(cityA, 30),
      } as Response);
    });

    const controller = new AbortController();
    await api.getCurrentAirQuality(
      { lat: cityA.latitude, lon: cityA.longitude, city: cityA.name, standard: 'US_EPA' },
      { signal: controller.signal }
    );
    expect(capturedInit?.signal).toBe(controller.signal);
  });
});
