import React, { useState } from 'react';
import { useAQI } from '../../context/AQIContext';
import { AQIStandard } from '../../types/airQuality';
import {
  Activity,
  Footprints,
  Bike,
  Dumbbell,
  Briefcase,
  HeartPulse,
  Info,
  Home,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';

export type AdvisorActivityId = 'running' | 'cycling' | 'walking' | 'labor' | 'sensitive';
export type EaqiBand = 1 | 2 | 3 | 4 | 5 | 6;

export interface ActivityGuidanceOptions {
  band?: number | null;
}

export interface ActivitySafetyAssessment {
  level: 'Safe & Optimal' | 'Caution Advised' | 'High Risk' | 'Unavailable';
  color: string;
  badge: string;
  safe: boolean;
}

export interface ActivityAdvisoryItem {
  id: AdvisorActivityId;
  name: string;
  safety: ActivitySafetyAssessment;
  guidance: string;
}

const SUPPORTED_STANDARDS = new Set<AQIStandard>(['US_EPA', 'INDIA_CPCB', 'EUROPEAN_AQI']);

const SAFETY_STYLES: Record<ActivitySafetyAssessment['level'], ActivitySafetyAssessment> = {
  'Safe & Optimal': {
    level: 'Safe & Optimal',
    color: '#23966B',
    badge: 'bg-[#23966B]/15 text-[#23966B] border-[#23966B]/30',
    safe: true,
  },
  'Caution Advised': {
    level: 'Caution Advised',
    color: '#D5A33A',
    badge: 'bg-[#D5A33A]/15 text-[#D5A33A] border-[#D5A33A]/30',
    safe: true,
  },
  'High Risk': {
    level: 'High Risk',
    color: '#C94E55',
    badge: 'bg-[#C94E55]/15 text-[#C94E55] border-[#C94E55]/30',
    safe: false,
  },
  Unavailable: {
    level: 'Unavailable',
    color: '#647570',
    badge: 'bg-clima-subtle dark:bg-darkClima-subtle text-clima-muted dark:text-darkClima-muted border-clima-border dark:border-darkClima-border',
    safe: false,
  },
};

function makeSafety(level: ActivitySafetyAssessment['level']): ActivitySafetyAssessment {
  return { ...SAFETY_STYLES[level] };
}

/**
 * Resolves a valid finite non-negative AQI numeric value (preserving genuine 0), or returns null when unavailable.
 */
export function resolveAdvisorAqi(rawAqi: number | null | undefined): number | null {
  if (typeof rawAqi === 'number' && Number.isFinite(rawAqi) && rawAqi >= 0) {
    return rawAqi;
  }
  return null;
}

/**
 * Normalizes a requested AQI standard to one of the supported regulatory methodology keys, or null if unsupported/missing.
 */
export function resolveSupportedAdvisorStandard(standard?: string | null): AQIStandard | null {
  if (typeof standard !== 'string') return null;
  const trimmed = standard.trim() as AQIStandard;
  return SUPPORTED_STANDARDS.has(trimmed) ? trimmed : null;
}

/**
 * Maps an EAQI scaled score (0–100) and optional EEA band (1–6) onto the canonical EEA band 1..6.
 */
export function resolveEaqiBand(aqi: number, rawBand?: number | null): EaqiBand {
  let bandFromScore: EaqiBand;
  if (aqi <= 10) bandFromScore = 1;
  else if (aqi <= 30) bandFromScore = 2;
  else if (aqi <= 50) bandFromScore = 3;
  else if (aqi <= 70) bandFromScore = 4;
  else if (aqi <= 90) bandFromScore = 5;
  else bandFromScore = 6;

  if (typeof rawBand === 'number' && Number.isInteger(rawBand) && rawBand >= 1 && rawBand <= 6) {
    return Math.max(bandFromScore, rawBand) as EaqiBand;
  }
  return bandFromScore;
}

/**
 * Formats an AQI reading for display without substituting a fabricated fallback for missing values.
 */
export function formatAdvisorAqiDisplay(rawAqi: number | null | undefined): string {
  const valid = resolveAdvisorAqi(rawAqi);
  return valid !== null ? String(valid) : '—';
}

const ACTIVITY_META: Array<{
  id: AdvisorActivityId;
  name: string;
  epaThresholdLow: number;
  epaThresholdHigh: number;
  epaMediumGuidanceThreshold: number;
  highGuidance: string;
  mediumGuidance: string;
  lowGuidance: string;
}> = [
  {
    id: 'running',
    name: 'Running & Cardiovascular Workouts',
    epaThresholdLow: 100,
    epaThresholdHigh: 150,
    epaMediumGuidanceThreshold: 100,
    highGuidance:
      'Suspend intense outdoor running. High ventilation rates increase fine particulate deposition deep into alveolar lung tissues.',
    mediumGuidance:
      'Curtail duration and intensity. Schedule workouts in early morning before peak ozone and traffic-related NO₂.',
    lowGuidance:
      'Ideal conditions for outdoor cardiovascular training. Ambient particulate exposure poses minimal risk to pulmonary health.',
  },
  {
    id: 'cycling',
    name: 'Cycling & Active Urban Commute',
    epaThresholdLow: 120,
    epaThresholdHigh: 160,
    epaMediumGuidanceThreshold: 100,
    highGuidance:
      'Wear a certified N95 / FFP2 respirator with tight facial seal, or use climate-controlled mass transit.',
    mediumGuidance:
      'Choose designated low-traffic bike corridors or residential side streets to avoid concentrated tailpipe exhaust.',
    lowGuidance: 'Safe for cycling and urban commuting with normal precautions.',
  },
  {
    id: 'walking',
    name: 'Walking & Moderate Recreation',
    epaThresholdLow: 150,
    epaThresholdHigh: 200,
    epaMediumGuidanceThreshold: 150,
    highGuidance: 'Limit non-essential outdoor walking for all populations. Keep doors and windows closed.',
    mediumGuidance: 'Acceptable for healthy individuals; vulnerable demographics should limit outdoor exposure.',
    lowGuidance: 'Safe for walking, park recreation, and daily errands.',
  },
  {
    id: 'labor',
    name: 'Outdoor Labor & Construction',
    epaThresholdLow: 100,
    epaThresholdHigh: 200,
    epaMediumGuidanceThreshold: 100,
    highGuidance:
      'Mandatory particulate respirators and scheduled indoor rotation breaks for all on-site personnel.',
    mediumGuidance: 'Provide adequate hydration and monitor workers for acute respiratory irritation or eye fatigue.',
    lowGuidance: 'Standard workplace health and safety protocols apply.',
  },
  {
    id: 'sensitive',
    name: 'Sensitive Demographics (Asthma, Elderly, Pediatric)',
    epaThresholdLow: 50,
    epaThresholdHigh: 100,
    epaMediumGuidanceThreshold: 50,
    highGuidance:
      'Remain indoors with clean air filtration. Keep rapid-relief bronchodilator medication readily accessible.',
    mediumGuidance:
      'Noticeable symptoms like coughing or wheezing may emerge during prolonged exertion. Plan regular rest intervals.',
    lowGuidance: 'Clean atmospheric conditions. Standard daily outdoor activities are encouraged.',
  },
];

const UNAVAILABLE_ACTIVITY_GUIDANCE =
  'Air-quality-based activity guidance is unavailable because current AQI telemetry could not be verified.';

const UNSUPPORTED_STANDARD_GUIDANCE =
  'Activity risk classification cannot be confirmed because the selected AQI standard is unsupported or missing. Exercise caution with strenuous outdoor activity and check verified local advisories.';

const DEFAULT_ACTIVITY_BY_ID = Object.fromEntries(
  ACTIVITY_META.map((cfg) => [cfg.id, cfg])
) as Record<AdvisorActivityId, (typeof ACTIVITY_META)[number]>;

function assessEpaSafetyLevel(aqi: number, thresholdLow: number, thresholdHigh: number): ActivitySafetyAssessment {
  if (aqi > thresholdHigh) return makeSafety('High Risk');
  if (aqi > thresholdLow) return makeSafety('Caution Advised');
  return makeSafety('Safe & Optimal');
}

function assessEaqiActivity(
  activityId: AdvisorActivityId,
  band: EaqiBand
): { level: ActivitySafetyAssessment['level']; guidance: string } {
  const cfg = DEFAULT_ACTIVITY_BY_ID[activityId];
  if (band <= 2) {
    return { level: 'Safe & Optimal', guidance: cfg.lowGuidance };
  }
  if (band === 3) {
    if (activityId === 'sensitive') {
      return {
        level: 'Caution Advised',
        guidance:
          'Air quality is moderate (EAQI Band 3). Sensitive individuals should observe symptoms and plan regular rest intervals.',
      };
    }
    return { level: 'Safe & Optimal', guidance: cfg.lowGuidance };
  }
  if (band === 4) {
    if (activityId === 'sensitive') {
      return {
        level: 'High Risk',
        guidance:
          'Air quality is poor (EAQI Band 4). Sensitive individuals should reduce intense outdoor activities and remain indoors with clean air filtration.',
      };
    }
    return { level: 'Caution Advised', guidance: cfg.mediumGuidance };
  }
  if (band === 5) {
    if (activityId === 'walking' || activityId === 'labor') {
      return { level: 'Caution Advised', guidance: cfg.mediumGuidance };
    }
    return { level: 'High Risk', guidance: cfg.highGuidance };
  }
  // Band 6: Extremely Poor — reduce outdoor physical activity for everyone
  return { level: 'High Risk', guidance: cfg.highGuidance };
}

function assessCpcbActivity(
  activityId: AdvisorActivityId,
  aqi: number
): { level: ActivitySafetyAssessment['level']; guidance: string } {
  const cfg = DEFAULT_ACTIVITY_BY_ID[activityId];
  // Official CPCB NAQI categories: Good (<=50), Satisfactory (51-100), Moderate (101-200),
  // Poor (201-300), Very Poor (301-400), Severe (>400).
  if (aqi <= 50) {
    return { level: 'Safe & Optimal', guidance: cfg.lowGuidance };
  }
  if (aqi <= 100) {
    if (activityId === 'sensitive') {
      return {
        level: 'Caution Advised',
        guidance:
          'Minor breathing discomfort possible for sensitive people under CPCB Satisfactory conditions. Monitor symptoms during prolonged exertion.',
      };
    }
    return { level: 'Safe & Optimal', guidance: cfg.lowGuidance };
  }
  if (aqi <= 200) {
    if (activityId === 'sensitive') {
      return {
        level: 'High Risk',
        guidance:
          'Breathing discomfort likely for people with lung, asthma, or heart conditions. Limit outdoor exposure and keep clean indoor filtration active.',
      };
    }
    return { level: 'Caution Advised', guidance: cfg.mediumGuidance };
  }
  if (aqi <= 300) {
    if (activityId === 'walking' || activityId === 'labor') {
      return { level: 'Caution Advised', guidance: cfg.mediumGuidance };
    }
    return { level: 'High Risk', guidance: cfg.highGuidance };
  }
  // Very Poor (301-400) and Severe (>400): respiratory illness on prolonged exposure / affects healthy people
  return { level: 'High Risk', guidance: cfg.highGuidance };
}

/**
 * Evaluates activity safety classification strictly under the supplied AQI standard scale.
 * Never reuses US EPA thresholds for EAQI/CPCB, and returns Unavailable when AQI or standard is missing/unsupported.
 */
export function getActivitySafetyLevel(
  rawAqi: number | null | undefined,
  thresholdLow: number,
  thresholdHigh: number,
  standard?: string | null,
  activityId: AdvisorActivityId = 'running',
  options?: ActivityGuidanceOptions
): ActivitySafetyAssessment {
  const aqi = resolveAdvisorAqi(rawAqi);
  const resolvedStandard = resolveSupportedAdvisorStandard(standard);
  if (aqi === null || resolvedStandard === null) {
    return makeSafety('Unavailable');
  }
  if (resolvedStandard === 'US_EPA') {
    return assessEpaSafetyLevel(aqi, thresholdLow, thresholdHigh);
  }
  if (resolvedStandard === 'EUROPEAN_AQI') {
    const band = resolveEaqiBand(aqi, options?.band);
    return makeSafety(assessEaqiActivity(activityId, band).level);
  }
  return makeSafety(assessCpcbActivity(activityId, aqi).level);
}

/**
 * Builds outdoor activity risk assessments calibrated to the active AQI standard,
 * returning non-reassuring unavailable guidance whenever AQI or standard is missing/unsupported.
 */
export function buildActivityAdvisories(
  rawAqi: number | null | undefined,
  standard?: string | null,
  options?: ActivityGuidanceOptions
): ActivityAdvisoryItem[] {
  const aqi = resolveAdvisorAqi(rawAqi);
  const resolvedStandard = resolveSupportedAdvisorStandard(standard);

  return ACTIVITY_META.map((cfg) => {
    if (aqi === null) {
      return {
        id: cfg.id,
        name: cfg.name,
        safety: makeSafety('Unavailable'),
        guidance: UNAVAILABLE_ACTIVITY_GUIDANCE,
      };
    }
    if (resolvedStandard === null) {
      return {
        id: cfg.id,
        name: cfg.name,
        safety: makeSafety('Unavailable'),
        guidance: UNSUPPORTED_STANDARD_GUIDANCE,
      };
    }
    if (resolvedStandard === 'US_EPA') {
      return {
        id: cfg.id,
        name: cfg.name,
        safety: assessEpaSafetyLevel(aqi, cfg.epaThresholdLow, cfg.epaThresholdHigh),
        guidance:
          aqi > cfg.epaThresholdHigh
            ? cfg.highGuidance
            : aqi > cfg.epaMediumGuidanceThreshold
            ? cfg.mediumGuidance
            : cfg.lowGuidance,
      };
    }
    if (resolvedStandard === 'EUROPEAN_AQI') {
      const band = resolveEaqiBand(aqi, options?.band);
      const assessed = assessEaqiActivity(cfg.id, band);
      return {
        id: cfg.id,
        name: cfg.name,
        safety: makeSafety(assessed.level),
        guidance: assessed.guidance,
      };
    }
    const assessed = assessCpcbActivity(cfg.id, aqi);
    return {
      id: cfg.id,
      name: cfg.name,
      safety: makeSafety(assessed.level),
      guidance: assessed.guidance,
    };
  });
}

/**
 * Returns indoor ventilation guidance calibrated to the active AQI standard without recommending
 * window ventilation during elevated pollution or when telemetry/standard cannot be verified.
 */
export function getIndoorMitigationGuidance(
  rawAqi: number | null | undefined,
  standard?: string | null,
  options?: ActivityGuidanceOptions
): string {
  const aqi = resolveAdvisorAqi(rawAqi);
  if (aqi === null) {
    return 'Current AQI telemetry is unavailable. Check local environmental monitoring alerts before adjusting indoor ventilation or filtration.';
  }
  const resolvedStandard = resolveSupportedAdvisorStandard(standard);
  if (resolvedStandard === null) {
    return 'The current AQI standard scale could not be verified. Keep indoor air clean and verify local environmental advisories before opening windows for ventilation.';
  }

  const closedFiltrationMsg =
    'Keep windows and doors closed during elevated pollution or peak traffic hours. Deploy True HEPA (H13/H14) air filtration units to remove fine particles down to 0.3 µm.';
  const ventilateMsg =
    'Ventilate living and working spaces with fresh air during low-traffic afternoon periods to prevent indoor CO₂ buildup.';

  if (resolvedStandard === 'EUROPEAN_AQI') {
    const band = resolveEaqiBand(aqi, options?.band);
    return band >= 4 ? closedFiltrationMsg : ventilateMsg;
  }

  // Both US_EPA (>100 = USG/Unhealthy/Very Unhealthy/Hazardous) and INDIA_CPCB (>100 = Moderate/Poor/Very Poor/Severe)
  return aqi > 100 ? closedFiltrationMsg : ventilateMsg;
}

const ACTIVITY_ICONS: Record<AdvisorActivityId, React.ComponentType<{ className?: string }>> = {
  running: Dumbbell,
  cycling: Bike,
  walking: Footprints,
  labor: Briefcase,
  sensitive: HeartPulse,
};

export const HealthAdvisorView: React.FC = () => {
  const { airQuality, activeCity, standard, loading, error, refreshData } = useAQI();
  const [selectedActivityKey, setSelectedActivityKey] = useState<string>('all');

  if (loading && !airQuality) {
    return (
      <div className="h-[55vh] flex flex-col items-center justify-center space-y-4">
        <RefreshCw className="w-8 h-8 text-clima-accent dark:text-darkClima-accent animate-spin" />
        <span className="text-xs font-mono text-clima-muted dark:text-darkClima-muted tracking-wider">
          Loading environmental health advisories for {activeCity.name}...
        </span>
      </div>
    );
  }

  if (!airQuality) {
    return (
      <div className="max-w-2xl mx-auto my-12 p-6 rounded-xl border border-clima-border dark:border-darkClima-border bg-clima-surface dark:bg-darkClima-surface text-center space-y-4 shadow-floating dark:shadow-floating-dark font-sans">
        <div className="w-10 h-10 rounded-full bg-red-500/10 text-red-500 flex items-center justify-center mx-auto">
          <AlertTriangle className="w-5 h-5" />
        </div>
        <div className="space-y-1">
          <h3 className="text-sm font-bold text-clima-text dark:text-darkClima-text">
            Health Guidance Unavailable
          </h3>
          <p className="text-xs text-clima-muted dark:text-darkClima-muted">
            {error || `Environmental telemetry for ${activeCity.name} is temporarily unavailable.`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => refreshData()}
          className="px-4 py-2 bg-clima-accent dark:bg-darkClima-accent text-white dark:text-darkClima-bg text-xs font-medium rounded-lg hover:opacity-90 transition-opacity"
        >
          Retry Telemetry Fetch
        </button>
      </div>
    );
  }

  const resolvedStandard = resolveSupportedAdvisorStandard(standard);
  const currentResult = resolvedStandard ? airQuality.aqi_standard_results?.[resolvedStandard] : undefined;
  const aqi = resolvedStandard ? resolveAdvisorAqi(currentResult?.aqi) : null;
  const displayAqi = formatAdvisorAqiDisplay(aqi);
  const dominant =
    aqi !== null
      ? currentResult?.dominant_pollutant || airQuality.dominant_pollutant || 'Unavailable'
      : currentResult?.dominant_pollutant || 'Unavailable';
  const bannerColor = aqi !== null ? (currentResult?.color || '#23966B') : '#647570';
  const displayCategory = aqi !== null ? (currentResult?.category || 'Unavailable') : 'Unavailable';
  const displayAdvisory =
    aqi !== null
      ? (currentResult?.advisory || 'Air quality health advisory is currently unavailable.')
      : resolvedStandard === null
      ? 'Air-quality-based risk classification is unavailable because the selected AQI standard is unsupported.'
      : 'Air-quality-based risk classification cannot be determined without a valid AQI reading.';

  const advisorOptions: ActivityGuidanceOptions = { band: currentResult?.band };
  const activities = buildActivityAdvisories(aqi, standard, advisorOptions).map((item) => ({
    ...item,
    icon: ACTIVITY_ICONS[item.id],
  }));

  const filteredActivities = selectedActivityKey === 'all' ? activities : activities.filter(a => a.id === selectedActivityKey);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12 font-sans">
      {/* Header */}
      <div className="border-b border-clima-border dark:border-darkClima-border pb-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-clima-subtle dark:bg-darkClima-subtle rounded-lg text-clima-accent dark:text-darkClima-accent border border-clima-border dark:border-darkClima-border">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-clima-text dark:text-darkClima-text tracking-tight font-sans">
                Environmental Health & Activity Risk Advisory
              </h2>
              <p className="text-xs text-clima-muted dark:text-darkClima-muted mt-0.5">
                Evidence-based outdoor activity risk assessment calibrated to {activeCity.name} (Current {standard.replace('_', ' ')} AQI:{' '}
                <span className="font-mono font-bold text-clima-text dark:text-darkClima-text underline decoration-2" style={{ textDecorationColor: bannerColor }}>
                  {displayAqi}
                </span>
                , Dominant: <span className="font-mono text-clima-accent dark:text-darkClima-accent">{dominant}</span>).
              </p>
            </div>
          </div>
        </div>

        {/* Activity Filter Buttons */}
        <div className="flex items-center space-x-1 overflow-x-auto bg-clima-subtle dark:bg-darkClima-subtle p-1 rounded-lg border border-clima-border dark:border-darkClima-border text-xs">
          <button
            onClick={() => setSelectedActivityKey('all')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              selectedActivityKey === 'all'
                ? 'bg-clima-surface dark:bg-darkClima-surface text-clima-accent dark:text-darkClima-accent font-semibold shadow-sm'
                : 'text-clima-muted dark:text-darkClima-muted hover:text-clima-text'
            }`}
          >
            All Activities
          </button>
          {activities.map((a) => (
            <button
              key={a.id}
              onClick={() => setSelectedActivityKey(a.id)}
              className={`px-2.5 py-1 rounded-md transition-colors whitespace-nowrap ${
                selectedActivityKey === a.id
                  ? 'bg-clima-surface dark:bg-darkClima-surface text-clima-accent dark:text-darkClima-accent font-semibold shadow-sm'
                  : 'text-clima-muted dark:text-darkClima-muted hover:text-clima-text'
              }`}
            >
              {a.name.split(' ')[0]}
            </button>
          ))}
        </div>
      </div>

      {/* Advisory Banner */}
      <div
        className="p-5 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-floating dark:shadow-floating-dark"
        style={{
          backgroundColor: `${bannerColor}10`,
          borderColor: `${bannerColor}35`,
        }}
      >
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span
              className="text-xs font-bold uppercase tracking-wider font-mono px-2 py-0.5 rounded"
              style={{ backgroundColor: `${bannerColor}25`, color: bannerColor }}
            >
              {displayCategory}
            </span>
            <span className="text-xs text-clima-muted dark:text-darkClima-muted">Official Health Advisory</span>
          </div>
          <p className="text-sm font-medium text-clima-text dark:text-darkClima-text">{displayAdvisory}</p>
        </div>

        <div className="shrink-0 flex items-center space-x-4">
          <div className="text-right">
            <span className="text-[10px] text-clima-muted dark:text-darkClima-muted uppercase tracking-widest block font-mono">Index</span>
            <span className="text-3xl font-extrabold font-mono" style={{ color: bannerColor }}>
              {displayAqi}
            </span>
          </div>
        </div>
      </div>

      {/* Activity Assessment Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {filteredActivities.map((act, idx) => {
          const Icon = act.icon;
          return (
            <div
              key={idx}
              className="rounded-xl p-5 border border-clima-border dark:border-darkClima-border bg-clima-surface dark:bg-darkClima-surface space-y-3.5 transition-all shadow-floating dark:shadow-floating-dark"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  <div className="p-2 bg-clima-subtle dark:bg-darkClima-subtle rounded-lg text-clima-text dark:text-darkClima-text border border-clima-border dark:border-darkClima-border">
                    <Icon className="w-4 h-4" />
                  </div>
                  <h3 className="text-sm font-bold text-clima-text dark:text-darkClima-text font-sans">{act.name}</h3>
                </div>
                <span className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-full border ${act.safety.badge} font-mono`}>
                  {act.safety.level}
                </span>
              </div>

              <p className="text-xs text-clima-muted dark:text-darkClima-muted leading-relaxed font-sans">{act.guidance}</p>
            </div>
          );
        })}

        {/* Indoor Air Quality & Mitigation Card */}
        <div className="rounded-xl p-5 border border-clima-border dark:border-darkClima-border bg-clima-surface dark:bg-darkClima-surface space-y-3.5 shadow-floating dark:shadow-floating-dark">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="p-2 bg-clima-subtle dark:bg-darkClima-subtle rounded-lg text-clima-accent dark:text-darkClima-accent border border-clima-border dark:border-darkClima-border">
                <Home className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-bold text-clima-text dark:text-darkClima-text font-sans">Indoor Air Quality & Filtration</h3>
            </div>
            <span className="text-[10px] font-semibold px-2.5 py-0.5 rounded-full bg-clima-subtle dark:bg-darkClima-subtle text-clima-text dark:text-darkClima-text border border-clima-border dark:border-darkClima-border font-mono">
              Mitigation
            </span>
          </div>
          <p className="text-xs text-clima-muted dark:text-darkClima-muted leading-relaxed font-sans">
            {getIndoorMitigationGuidance(aqi, standard, advisorOptions)}
          </p>
        </div>
      </div>

      {/* Medical Disclaimer Note */}
      <div className="p-4 bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-xl flex items-start space-x-3 text-clima-muted dark:text-darkClima-muted text-xs">
        <Info className="w-4 h-4 text-clima-accent dark:text-darkClima-accent shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          <strong className="text-clima-text dark:text-darkClima-text">Non-Diagnostic Guidance:</strong> AeroSense health advisories are synthesized from published public health standards (WHO Global Air Quality Guidelines and US EPA National Ambient Air Quality Standards). This information is environmental guidance for healthy exposure management and does not constitute individualized medical diagnosis or treatment.
        </p>
      </div>
    </div>
  );
};
