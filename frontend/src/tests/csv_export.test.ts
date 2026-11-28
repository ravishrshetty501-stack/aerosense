import { describe, it, expect } from 'vitest';
import {
  TrajectoryChartPoint,
  buildTrajectoryCsv,
  formatFiniteDecimal,
  sanitizeDownloadFilename,
} from '../utils/airQualityHelpers';

describe('AeroSense AI Phase D.3.2.1 Numeric Formatting, CSV Security & Filename Sanitization', () => {
  it('formats finite decimals preserving zero while returning fallback for non-finite and non-numeric inputs', () => {
    expect(formatFiniteDecimal(0)).toBe('0.0');
    expect(formatFiniteDecimal(-0)).toBe('0.0');
    expect(formatFiniteDecimal(42.56)).toBe('42.6');
    expect(formatFiniteDecimal(-3.14)).toBe('-3.1');

    expect(formatFiniteDecimal(null)).toBe('—');
    expect(formatFiniteDecimal(undefined)).toBe('—');
    expect(formatFiniteDecimal(Number.NaN)).toBe('—');
    expect(formatFiniteDecimal(Number.POSITIVE_INFINITY)).toBe('—');
    expect(formatFiniteDecimal(Number.NEGATIVE_INFINITY)).toBe('—');
    expect(formatFiniteDecimal('42.5' as unknown)).toBe('—');
    expect(formatFiniteDecimal({}, 1, 'N/A')).toBe('N/A');
  });

  it('includes UTF-8 BOM, CRLF separators, Unicode labels/units, empty cells for invalid numbers, and preserves valid negative & zero numerics', () => {
    const points: TrajectoryChartPoint[] = [
      {
        time: '11/20, 14:00',
        isoTime: '2026-11-20T14:00:00Z',
        observed: 0,
        forecast: null,
        isForecast: false,
        pm25: 0,
        pm10: null,
        no2: null,
        o3: 0,
      },
      {
        time: '11/20, 15:00',
        isoTime: '2026-11-20T15:00:00Z',
        observed: -5.4,
        forecast: Number.NaN,
        isForecast: false,
        pm25: null,
        pm10: null,
        no2: null,
        o3: null,
      },
      {
        time: '11/20, 16:00',
        isoTime: '2026-11-20T16:00:00Z',
        observed: Number.POSITIVE_INFINITY,
        forecast: undefined as unknown as number | null,
        isForecast: true,
        pm25: null,
        pm10: null,
        no2: null,
        o3: null,
      },
    ];

    const csv = buildTrajectoryCsv(points, 'O₃', 'µg/m³');
    expect(csv.startsWith('\uFEFF')).toBe(true);
    expect(csv).not.toContain('\n\n');
    const lines = csv.slice(1).split('\r\n');
    expect(lines.length).toBe(4);
    expect(lines[0]).toBe('Timestamp,Pollutant,Observed_Conc,Forecast_Conc,Unit,Type');
    expect(lines[1]).toBe('"2026-11-20T14:00:00Z","O₃",0,,"µg/m³","Observed"');
    // Valid negative numbers remain numeric without apostrophe prefix
    expect(lines[2]).toBe('"2026-11-20T15:00:00Z","O₃",-5.4,,"µg/m³","Observed"');
    // Non-finite / undefined render empty numeric cells
    expect(lines[3]).toBe('"2026-11-20T16:00:00Z","O₃",,,"µg/m³","Forecast"');
  });

  it('neutralizes spreadsheet formula-injection triggers and leading whitespace/control-char evasions before RFC 4180 quoting', () => {
    const basePoint = (isoTime: string): TrajectoryChartPoint => ({
      time: 'fallback',
      isoTime,
      observed: 12.3,
      forecast: null,
      isForecast: false,
      pm25: 12.3,
      pm10: null,
      no2: null,
      o3: null,
    });

    const csv = buildTrajectoryCsv(
      [
        basePoint('=CMD("calc")'),
        basePoint('+SUM(A1:A2)'),
        basePoint('-10+cmd'),
        basePoint('@SUM(1,1)'),
        basePoint('\t=HYPERLINK("https://bad.test")'),
        basePoint('\r=1+1'),
        basePoint('   =2+2'),
        basePoint('\n+cmd'),
        basePoint('2026-11-20 "quoted", comma\nline2'),
      ],
      'NO₂',
      '=badUnit'
    );

    const lines = csv.slice(1).split('\r\n');
    expect(lines[1]).toContain('"\'=CMD(""calc"")","NO₂",12.3,,"' + "'=badUnit" + '","Observed"');
    expect(lines[2]).toContain('"\'+SUM(A1:A2)"');
    expect(lines[3]).toContain('"\'-10+cmd"');
    expect(lines[4]).toContain('"\'@SUM(1,1)"');
    expect(lines[5]).toContain('"\'\t=HYPERLINK(""https://bad.test"")"');
    expect(lines[6]).toContain('"\'\r=1+1"');
    expect(lines[7]).toContain('"\'   =2+2"');
    expect(lines[8]).toContain('"\'\n+cmd"');
    expect(csv).toContain('"2026-11-20 ""quoted"", comma\nline2"');
  });

  it('sanitizes download filenames removing path separators, control chars, traversal dots, and preserving .csv extension', () => {
    expect(sanitizeDownloadFilename('New York')).toBe('New_York.csv');
    expect(sanitizeDownloadFilename('../../../etc/passwd')).toBe('etc_passwd.csv');
    expect(sanitizeDownloadFilename('Tokyo\r\n\0/\\:*?"<>|')).toBe('Tokyo.csv');
    expect(sanitizeDownloadFilename('')).toBe('AeroSense_Export.csv');
    expect(sanitizeDownloadFilename('...///...')).toBe('AeroSense_Export.csv');
    expect(sanitizeDownloadFilename('Delhi_o3', '.csv')).toBe('Delhi_o3.csv');

    const unsafeCity = sanitizeDownloadFilename('..\\evil/city\r\n', '', 'location');
    expect(unsafeCity).toBe('evil_city');
    expect(sanitizeDownloadFilename('///', '', 'location')).toBe('location');
  });
});
