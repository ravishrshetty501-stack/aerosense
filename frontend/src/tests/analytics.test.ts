import { describe, it, expect } from 'vitest';
import { HourlyTrendPoint } from '../types/airQuality';
import {
  buildTrajectorySeries,
  hasValidTrajectoryData,
  selectChartBDistribution,
} from '../utils/airQualityHelpers';

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

  it('1. correctly transforms contiguous trajectory when both history and forecast exist', () => {
    const { combinedTrajectory: trajectory } = buildTrajectorySeries(sampleHistory, sampleForecast, 'o3');
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
    const { combinedTrajectory: trajectory } = buildTrajectorySeries(sampleHistory, [], 'o3');
    expect(trajectory.length).toBe(3);
    expect(trajectory[0].observed).toBe(28.5);
    expect(trajectory[1].observed).toBe(29.6);
    expect(trajectory[2].observed).toBe(31.0);
    // Zero forecast values should be fabricated
    expect(trajectory.every((p) => p.forecast === null)).toBe(true);
  });

  it('3. preserves forecast values when historical data is missing', () => {
    const { combinedTrajectory: trajectory } = buildTrajectorySeries([], sampleForecast, 'o3');
    expect(trajectory.length).toBe(2);
    expect(trajectory[0].forecast).toBe(33.2);
    expect(trajectory[1].forecast).toBe(34.0);
    // Zero historical values should be fabricated
    expect(trajectory.every((p) => p.observed === null)).toBe(true);
  });

  it('4. ensures partial pollutant data does not hide other available series', () => {
    const partialData: HourlyTrendPoint[] = [
      { time: '2026-11-20T14:00:00Z', pm25: 45.2, pm10: 68.1, no2: undefined, o3: 28.5, is_forecast: false, type: 'model_estimate' },
      { time: '2026-11-20T15:00:00Z', pm25: 48.0, pm10: undefined, no2: 26.0, o3: undefined, is_forecast: false, type: 'model_estimate' },
    ];

    const pm25Trajectory = buildTrajectorySeries(partialData, [], 'pm25').combinedTrajectory;
    const no2Trajectory = buildTrajectorySeries(partialData, [], 'no2').combinedTrajectory;
    const o3Trajectory = buildTrajectorySeries(partialData, [], 'o3').combinedTrajectory;

    expect(pm25Trajectory[0].observed).toBe(45.2);
    expect(pm25Trajectory[1].observed).toBe(48.0);

    expect(no2Trajectory[0].observed).toBeNull(); // Missing in point 0, but valid in point 1
    expect(no2Trajectory[1].observed).toBe(26.0);

    expect(o3Trajectory[0].observed).toBe(28.5);
    expect(o3Trajectory[1].observed).toBeNull();
  });

  it('5. detects empty state when neither history nor forecast are available', () => {
    const { combinedTrajectory: trajectory } = buildTrajectorySeries([], [], 'o3');
    expect(trajectory.length).toBe(0);
    expect(hasValidTrajectoryData(trajectory)).toBe(false);
  });

  it('6. sanitizes invalid, NaN, infinities, or non-numeric values without throwing while preserving zero', () => {
    const malformedData = [
      { time: 'invalid-time', pm25: NaN, pm10: null, no2: 'not-a-number', o3: undefined, is_forecast: false, type: 'bad' },
      { time: 'inf-time', pm25: Number.POSITIVE_INFINITY, pm10: Number.NEGATIVE_INFINITY, no2: 0, o3: 0, is_forecast: false, type: 'inf' },
    ] as unknown as HourlyTrendPoint[];

    const { combinedTrajectory: pm25Traj } = buildTrajectorySeries(malformedData, [], 'pm25');
    expect(pm25Traj.length).toBe(2);
    expect(pm25Traj[0].observed).toBeNull();
    expect(pm25Traj[1].observed).toBeNull();
    expect(hasValidTrajectoryData(pm25Traj)).toBe(false);

    const { combinedTrajectory: no2Traj } = buildTrajectorySeries(malformedData, [], 'no2');
    expect(no2Traj[0].observed).toBeNull();
    expect(no2Traj[1].observed).toBe(0);
    expect(hasValidTrajectoryData(no2Traj)).toBe(true);

    // Direct non-finite trajectory check rejects ±Infinity
    expect(
      hasValidTrajectoryData([
        {
          time: 't',
          isoTime: 't',
          observed: Number.POSITIVE_INFINITY,
          forecast: Number.NEGATIVE_INFINITY,
          isForecast: false,
          pm25: null,
          pm10: null,
          no2: null,
          o3: null,
        },
      ])
    ).toBe(false);
  });

  it('7. selects recent 18 hours of observed history for multi-pollutant distribution', () => {
    const longHistory: HourlyTrendPoint[] = Array.from({ length: 24 }, (_, i) => ({
      time: `2026-11-20T${String(i).padStart(2, '0')}:00:00Z`,
      pm25: 20 + i,
      pm10: 40 + i,
      no2: 10 + i,
      o3: 15 + i,
      is_forecast: false,
      type: 'model_estimate',
    }));

    const { historySeries, forecastSeries } = buildTrajectorySeries(longHistory, sampleForecast, 'pm25');
    const recent18 = selectChartBDistribution(historySeries, forecastSeries);
    expect(recent18.length).toBe(18);
    expect(recent18[0].pm25).toBe(26); // hour 6 (20 + 6)
    expect(recent18[17].pm25).toBe(43); // hour 23 (20 + 23)
  });

  it('8. falls back to first 18 forecast hours for Chart B only when observed history is absent', () => {
    const longForecast: HourlyTrendPoint[] = Array.from({ length: 24 }, (_, i) => ({
      time: `2026-11-21T${String(i).padStart(2, '0')}:00:00Z`,
      pm25: 10 + i,
      pm10: 20 + i,
      no2: 5 + i,
      o3: 15 + i,
      is_forecast: true,
      type: 'forecast',
    }));

    const { historySeries, forecastSeries } = buildTrajectorySeries([], longForecast, 'pm25');
    const chartB = selectChartBDistribution(historySeries, forecastSeries);
    expect(chartB.length).toBe(18);
    expect(chartB[0].pm25).toBe(10);
    expect(chartB[17].pm25).toBe(27);
  });
});
