import { describe, it, expect } from 'vitest';
import {
  resolveAdvisorAqi,
  resolveSupportedAdvisorStandard,
  resolveEaqiBand,
  formatAdvisorAqiDisplay,
  getActivitySafetyLevel,
  buildActivityAdvisories,
  getIndoorMitigationGuidance,
} from '../components/advisor/HealthAdvisorView';

describe('HealthAdvisorView zero, valid, null, and non-finite AQI handling', () => {
  it('preserves genuine 0 AQI without coercing to 50 and classifies US_EPA thresholds accurately', () => {
    expect(resolveAdvisorAqi(0)).toBe(0);
    expect(formatAdvisorAqiDisplay(0)).toBe('0');

    const zeroActivities = buildActivityAdvisories(0, 'US_EPA');
    expect(zeroActivities.every((a) => a.safety.level === 'Safe & Optimal')).toBe(true);
    expect(getIndoorMitigationGuidance(0, 'US_EPA')).toContain('Ventilate');

    // US_EPA boundaries around 50, 100, 120, 150, 160, 200
    expect(resolveAdvisorAqi(50)).toBe(50);
    expect(formatAdvisorAqiDisplay(50)).toBe('50');
    expect(buildActivityAdvisories(50, 'US_EPA').every((a) => a.safety.level === 'Safe & Optimal')).toBe(true);

    const aqi51 = buildActivityAdvisories(51, 'US_EPA');
    expect(aqi51.find((a) => a.id === 'sensitive')?.safety.level).toBe('Caution Advised');
    expect(aqi51.find((a) => a.id === 'running')?.safety.level).toBe('Safe & Optimal');

    const aqi100 = buildActivityAdvisories(100, 'US_EPA');
    expect(aqi100.find((a) => a.id === 'sensitive')?.safety.level).toBe('Caution Advised');
    expect(aqi100.find((a) => a.id === 'running')?.safety.level).toBe('Safe & Optimal');
    expect(getIndoorMitigationGuidance(100, 'US_EPA')).toContain('Ventilate');

    const aqi101 = buildActivityAdvisories(101, 'US_EPA');
    expect(aqi101.find((a) => a.id === 'running')?.safety.level).toBe('Caution Advised');
    expect(aqi101.find((a) => a.id === 'labor')?.safety.level).toBe('Caution Advised');
    expect(aqi101.find((a) => a.id === 'sensitive')?.safety.level).toBe('High Risk');
    expect(getIndoorMitigationGuidance(101, 'US_EPA')).toContain('HEPA');
    expect(getIndoorMitigationGuidance(101, 'US_EPA').toLowerCase()).toContain('closed');

    const aqi151 = buildActivityAdvisories(151, 'US_EPA');
    expect(aqi151.find((a) => a.id === 'running')?.safety.level).toBe('High Risk');
    expect(aqi151.find((a) => a.id === 'walking')?.safety.level).toBe('Caution Advised');

    const aqi200 = buildActivityAdvisories(200, 'US_EPA');
    expect(aqi200.find((a) => a.id === 'running')?.safety.level).toBe('High Risk');
    expect(aqi200.find((a) => a.id === 'cycling')?.safety.level).toBe('High Risk');
    expect(aqi200.find((a) => a.id === 'walking')?.safety.level).toBe('Caution Advised');
    expect(aqi200.find((a) => a.id === 'labor')?.safety.level).toBe('Caution Advised');
    expect(aqi200.find((a) => a.id === 'sensitive')?.safety.level).toBe('High Risk');
    expect(getIndoorMitigationGuidance(200, 'US_EPA')).toContain('HEPA');

    const aqi201 = buildActivityAdvisories(201, 'US_EPA');
    expect(aqi201.every((a) => a.safety.level === 'High Risk' && !a.safety.safe)).toBe(true);
  });

  it('displays unavailable and never falls back to 50 or Safe & Optimal for null, undefined, NaN, Infinity, or negative inputs', () => {
    const missingInputs: Array<number | null | undefined> = [
      null,
      undefined,
      Number.NaN,
      Number.POSITIVE_INFINITY,
      Number.NEGATIVE_INFINITY,
      -1,
    ];

    for (const rawAqi of missingInputs) {
      expect(resolveAdvisorAqi(rawAqi)).toBeNull();
      expect(formatAdvisorAqiDisplay(rawAqi)).toBe('—');

      for (const std of ['US_EPA', 'EUROPEAN_AQI', 'INDIA_CPCB'] as const) {
        const safety = getActivitySafetyLevel(rawAqi, 100, 150, std);
        expect(safety.level).toBe('Unavailable');
        expect(safety.safe).toBe(false);

        const advisories = buildActivityAdvisories(rawAqi, std);
        expect(advisories.every((a) => a.safety.level === 'Unavailable' && !a.safety.safe)).toBe(true);
        expect(advisories.every((a) => a.guidance.toLowerCase().includes('unavailable'))).toBe(true);

        const indoor = getIndoorMitigationGuidance(rawAqi, std).toLowerCase();
        expect(indoor).toContain('unavailable');
        expect(indoor).not.toContain('ventilate living and working spaces with fresh air');
      }
    }
  });
});

describe('HealthAdvisorView EUROPEAN_AQI band-based safety classification', () => {
  it('classifies every EEA EAQI band (1 through 6) using the 0-100 EAQI scale without US EPA thresholds', () => {
    // Band 1 (Good = 0) & Band 2 (Fair = 20)
    expect(resolveEaqiBand(0)).toBe(1);
    expect(resolveEaqiBand(20)).toBe(2);
    for (const score of [0, 20]) {
      const items = buildActivityAdvisories(score, 'EUROPEAN_AQI');
      expect(items.every((a) => a.safety.level === 'Safe & Optimal' && a.safety.safe)).toBe(true);
      expect(getIndoorMitigationGuidance(score, 'EUROPEAN_AQI')).toContain('Ventilate');
    }

    // Band 3 (Moderate = 40): sensitive groups advised caution, general activities safe
    expect(resolveEaqiBand(40)).toBe(3);
    const band3 = buildActivityAdvisories(40, 'EUROPEAN_AQI');
    expect(band3.find((a) => a.id === 'sensitive')?.safety.level).toBe('Caution Advised');
    expect(band3.find((a) => a.id === 'running')?.safety.level).toBe('Safe & Optimal');
    expect(getIndoorMitigationGuidance(40, 'EUROPEAN_AQI')).toContain('Ventilate');

    // Band 4 (Poor = 60): never Safe & Optimal, sensitive High Risk, indoor recommends closing windows + HEPA
    expect(resolveEaqiBand(60)).toBe(4);
    const band4 = buildActivityAdvisories(60, 'EUROPEAN_AQI');
    expect(band4.some((a) => a.safety.level === 'Safe & Optimal')).toBe(false);
    expect(band4.find((a) => a.id === 'sensitive')?.safety.level).toBe('High Risk');
    expect(band4.find((a) => a.id === 'running')?.safety.level).toBe('Caution Advised');
    const indoorBand4 = getIndoorMitigationGuidance(60, 'EUROPEAN_AQI');
    expect(indoorBand4).toContain('closed');
    expect(indoorBand4).toContain('HEPA');
    expect(indoorBand4).not.toContain('Ventilate living and working spaces');

    // Band 5 (Very Poor = 80): never Safe & Optimal; intense activities High Risk; windows closed + HEPA
    expect(resolveEaqiBand(80)).toBe(5);
    const band5 = buildActivityAdvisories(80, 'EUROPEAN_AQI');
    expect(band5.some((a) => a.safety.level === 'Safe & Optimal')).toBe(false);
    expect(band5.find((a) => a.id === 'running')?.safety.level).toBe('High Risk');
    expect(band5.find((a) => a.id === 'cycling')?.safety.level).toBe('High Risk');
    expect(band5.find((a) => a.id === 'sensitive')?.safety.level).toBe('High Risk');
    expect(band5.find((a) => a.id === 'walking')?.safety.level).toBe('Caution Advised');
    expect(band5.find((a) => a.id === 'labor')?.safety.level).toBe('Caution Advised');
    const indoorBand5 = getIndoorMitigationGuidance(80, 'EUROPEAN_AQI');
    expect(indoorBand5).toContain('closed');
    expect(indoorBand5).toContain('HEPA');

    // Band 6 (Extremely Poor = 100): every activity is High Risk (safe: false); windows closed + HEPA
    expect(resolveEaqiBand(100)).toBe(6);
    const band6 = buildActivityAdvisories(100, 'EUROPEAN_AQI');
    expect(band6.every((a) => a.safety.level === 'High Risk' && a.safety.safe === false)).toBe(true);
    const indoorBand6 = getIndoorMitigationGuidance(100, 'EUROPEAN_AQI');
    expect(indoorBand6).toContain('closed');
    expect(indoorBand6).toContain('HEPA');
    expect(indoorBand6.toLowerCase()).not.toContain('ventilate living and working spaces');
  });

  it('ignores US EPA thresholds passed directly to getActivitySafetyLevel when standard is EUROPEAN_AQI', () => {
    const runningBand5 = getActivitySafetyLevel(80, 100, 150, 'EUROPEAN_AQI', 'running');
    expect(runningBand5.level).toBe('High Risk');
    expect(runningBand5.safe).toBe(false);

    const runningBand6 = getActivitySafetyLevel(100, 100, 150, 'EUROPEAN_AQI', 'running');
    expect(runningBand6.level).toBe('High Risk');
    expect(runningBand6.safe).toBe(false);

    const walkingBand6 = getActivitySafetyLevel(100, 150, 200, 'EUROPEAN_AQI', 'walking');
    expect(walkingBand6.level).toBe('High Risk');
    expect(walkingBand6.safe).toBe(false);
  });
});

describe('HealthAdvisorView INDIA_CPCB standard-specific classification', () => {
  it('uses CPCB NAQI categories (Good/Satisfactory/Moderate/Poor/Very Poor/Severe) without EPA or EAQI thresholds', () => {
    // <=50 Good: all Safe & Optimal
    expect(buildActivityAdvisories(50, 'INDIA_CPCB').every((a) => a.safety.level === 'Safe & Optimal')).toBe(true);

    // 51-100 Satisfactory: sensitive Caution Advised, others Safe & Optimal
    const sat = buildActivityAdvisories(80, 'INDIA_CPCB');
    expect(sat.find((a) => a.id === 'sensitive')?.safety.level).toBe('Caution Advised');
    expect(sat.find((a) => a.id === 'running')?.safety.level).toBe('Safe & Optimal');
    expect(getIndoorMitigationGuidance(80, 'INDIA_CPCB')).toContain('Ventilate');

    // 101-200 Moderate: under CPCB, sensitive High Risk, others Caution Advised (uses 101-200 CPCB tier, not EPA 120/150/160)
    const mod155 = buildActivityAdvisories(155, 'INDIA_CPCB');
    expect(mod155.find((a) => a.id === 'running')?.safety.level).toBe('Caution Advised');
    expect(mod155.find((a) => a.id === 'cycling')?.safety.level).toBe('Caution Advised');
    expect(mod155.find((a) => a.id === 'walking')?.safety.level).toBe('Caution Advised');
    expect(mod155.find((a) => a.id === 'sensitive')?.safety.level).toBe('High Risk');
    expect(getIndoorMitigationGuidance(155, 'INDIA_CPCB')).toContain('closed');

    // 201-300 Poor: running/cycling/sensitive High Risk, walking/labor Caution Advised (distinct from EPA >200)
    const poor250 = buildActivityAdvisories(250, 'INDIA_CPCB');
    expect(poor250.find((a) => a.id === 'running')?.safety.level).toBe('High Risk');
    expect(poor250.find((a) => a.id === 'walking')?.safety.level).toBe('Caution Advised');
    expect(poor250.find((a) => a.id === 'labor')?.safety.level).toBe('Caution Advised');

    // 301-400 Very Poor & >400 Severe: all activities High Risk + closed/HEPA indoors
    for (const severeScore of [301, 450]) {
      const severe = buildActivityAdvisories(severeScore, 'INDIA_CPCB');
      expect(severe.every((a) => a.safety.level === 'High Risk' && !a.safety.safe)).toBe(true);
      const indoorSevere = getIndoorMitigationGuidance(severeScore, 'INDIA_CPCB');
      expect(indoorSevere).toContain('closed');
      expect(indoorSevere).toContain('HEPA');
    }
  });
});

describe('HealthAdvisorView unknown, missing, or unsupported standards', () => {
  it('never displays Safe & Optimal or recommends opening windows when standard is missing or unsupported', () => {
    const unsupportedStandards: Array<string | null | undefined> = [
      undefined,
      null,
      '',
      'UNKNOWN_STANDARD',
      'CHINA_MEP',
      'UK_DAQI',
    ];

    for (const std of unsupportedStandards) {
      expect(resolveSupportedAdvisorStandard(std)).toBeNull();

      for (const score of [0, 20, 80, 100]) {
        const safety = getActivitySafetyLevel(score, 100, 150, std, 'running');
        expect(safety.level).toBe('Unavailable');
        expect(safety.safe).toBe(false);

        const advisories = buildActivityAdvisories(score, std);
        expect(advisories.every((a) => a.safety.level === 'Unavailable' && !a.safety.safe)).toBe(true);
        expect(advisories.some((a) => a.safety.level === 'Safe & Optimal')).toBe(false);
        expect(advisories.every((a) => a.guidance.toLowerCase().includes('unsupported or missing'))).toBe(true);

        const indoor = getIndoorMitigationGuidance(score, std);
        expect(indoor.toLowerCase()).toContain('could not be verified');
        expect(indoor).not.toContain('Ventilate living and working spaces with fresh air');
      }
    }
  });
});
