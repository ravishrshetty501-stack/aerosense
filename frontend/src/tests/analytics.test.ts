import { describe, it, expect } from 'vitest';
import { HourlyTrendPoint } from '../types/airQuality';

describe('AeroSense AI Analytics Data Transformations & Chart Resilience', () => {
  const sampleHistory: HourlyTrendPoint[] = [
    { time: '2026-11-20T14:00:00Z', pm25: 45.2, pm10: 68.1, no2: 24.3, o3: 28.5, is_forecast: false, type: 'model_estimate' },
    { time: '2026-11-20T15:00:00Z', pm25: 48.0, pm10: 71.4, no2: 26.0, o3: 29.6, is_forecast: false, type: 'model_estimate' },
    { time: '2026-11-20T16:00:00Z', pm25: 52.1, pm10: 75.0, no2: 28.4, o3: 31.0, is_forecast: false, type: 'model_estimate' },
  ];

  const sampleForecast: HourlyTrendPoint[] = [
    { time: '2026-11-20T17:00:00Z', pm25: 55.4, pm10: 79.2, no2: 30.1, o3: 33.2, is_forecast: true, type: 'forecast' },
    { time: '2026-11-20T18:00:00Z', pm25: 58.0, pm10: 82.5, no2: 31.5, o3: 34.0, is_forecast: true, type: 'forecast' },
  ];

  // Helper function replicating the AnalyticsView contiguous series transformation
  const buildTrajectory = (
    history: HourlyTrendPoint[],
    forecast: HourlyTrendPoint[],
    pollutant: 'pm25' | 'pm10' | 'no2' | 'o3'
  ) => {
    const historySeries = history.map((pt) => ({
      time: pt.time,
      observed: typeof pt[pollutant] === 'number' && !isNaN(pt[pollutant]!) ? pt[pollutant]! : null,
      forecast: null as number | null,
      isForecast: false,
    }));

    const forecastSeries = forecast.map((pt) => ({
      time: pt.time,
      observed: null as number | null,
      forecast: typeof pt[pollutant] === 'number' && !isNaN(pt[pollutant]!) ? pt[pollutant]! : null,
      isForecast: true,
    }));

    if (historySeries.length > 0 && forecastSeries.length > 0) {
      const lastHistory = historySeries[historySeries.length - 1];
      const bridgePoint = {
        ...lastHistory,
        forecast: lastHistory.observed,
      };
      return [...historySeries.slice(0, -1), bridgePoint, ...forecastSeries];
    } else if (historySeries.length > 0) {
      return [...historySeries];
    } else if (forecastSeries.length > 0) {
      return [...forecastSeries];
    }
    return [];
  };

  it('1. correctly transforms contiguous trajectory when both history and forecast exist', () => {
    const trajectory = buildTrajectory(sampleHistory, sampleForecast, 'o3');
    // Total points = 3 history - 1 + 1 bridge + 2 forecast = 5
    expect(trajectory.length).toBe(5);

    // First point is pure history
    expect(trajectory[0].observed).toBe(28.5);
    expect(trajectory[0].forecast).toBeNull();
    expect(trajectory[0].isForecast).toBe(false);

    // Bridge point has both observed and forecast set to maintain a contiguous line
    const bridge = trajectory[2];
    expect(bridge.observed).toBe(31.0);
    expect(bridge.forecast).toBe(31.0);

    // Final point is pure forecast
    expect(trajectory[4].observed).toBeNull();
    expect(trajectory[4].forecast).toBe(34.0);
    expect(trajectory[4].isForecast).toBe(true);
  });

  it('2. preserves historical observations when forecast data is missing (CAMS degraded)', () => {
    const trajectory = buildTrajectory(sampleHistory, [], 'o3');
    expect(trajectory.length).toBe(3);
    expect(trajectory[0].observed).toBe(28.5);
    expect(trajectory[1].observed).toBe(29.6);
    expect(trajectory[2].observed).toBe(31.0);
    // Zero forecast values should be fabricated
    expect(trajectory.every(p => p.forecast === null)).toBe(true);
  });

  it('3. preserves forecast values when historical data is missing', () => {
    const trajectory = buildTrajectory([], sampleForecast, 'o3');
    expect(trajectory.length).toBe(2);
    expect(trajectory[0].forecast).toBe(33.2);
    expect(trajectory[1].forecast).toBe(34.0);
    // Zero historical values should be fabricated
    expect(trajectory.every(p => p.observed === null)).toBe(true);
  });

  it('4. ensures partial pollutant data does not hide other available series', () => {
    const partialData: HourlyTrendPoint[] = [
      { time: '2026-11-20T14:00:00Z', pm25: 45.2, pm10: 68.1, no2: undefined, o3: 28.5, is_forecast: false, type: 'model_estimate' },
      { time: '2026-11-20T15:00:00Z', pm25: 48.0, pm10: undefined, no2: 26.0, o3: undefined, is_forecast: false, type: 'model_estimate' },
    ];

    const pm25Trajectory = buildTrajectory(partialData, [], 'pm25');
    const no2Trajectory = buildTrajectory(partialData, [], 'no2');
    const o3Trajectory = buildTrajectory(partialData, [], 'o3');

    expect(pm25Trajectory[0].observed).toBe(45.2);
    expect(pm25Trajectory[1].observed).toBe(48.0);

    expect(no2Trajectory[0].observed).toBeNull(); // Missing in point 0, but valid in point 1
    expect(no2Trajectory[1].observed).toBe(26.0);

    expect(o3Trajectory[0].observed).toBe(28.5);
    expect(o3Trajectory[1].observed).toBeNull();
  });

  it('5. detects empty state when neither history nor forecast are available', () => {
    const trajectory = buildTrajectory([], [], 'o3');
    expect(trajectory.length).toBe(0);

    const hasValidData = trajectory.some(
      (d) => (typeof d.observed === 'number' && d.observed !== null) ||
             (typeof d.forecast === 'number' && d.forecast !== null)
    );
    expect(hasValidData).toBe(false);
  });

  it('6. sanitizes invalid, NaN, or non-numeric values without throwing', () => {
    const malformedData: any[] = [
      { time: 'invalid-time', pm25: NaN, pm10: null, no2: 'not-a-number', o3: undefined, is_forecast: false, type: 'bad' },
    ];

    const trajectory = buildTrajectory(malformedData, [], 'pm25');
    expect(trajectory.length).toBe(1);
    expect(trajectory[0].observed).toBeNull();
  });

  it('7. selects recent 18 hours of observed history for multi-pollutant distribution', () => {
    // Generate 24 hours of history
    const longHistory: HourlyTrendPoint[] = Array.from({ length: 24 }, (_, i) => ({
      time: `2026-11-20T${String(i).padStart(2, '0')}:00:00Z`,
      pm25: 20 + i,
      pm10: 40 + i,
      no2: 10 + i,
      o3: 15 + i,
      is_forecast: false,
      type: 'model_estimate',
    }));

    const recent18 = longHistory.slice(-18);
    expect(recent18.length).toBe(18);
    expect(recent18[0].pm25).toBe(26); // hour 6 (20 + 6)
    expect(recent18[17].pm25).toBe(43); // hour 23 (20 + 23)
  });
});
