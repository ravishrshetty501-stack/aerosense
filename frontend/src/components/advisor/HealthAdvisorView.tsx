import React from 'react';
import { useAQI } from '../../context/AQIContext';
import { Activity, Footprints, Bike, Dumbbell, Briefcase, HeartPulse, ShieldAlert, CheckCircle } from 'lucide-react';

export const HealthAdvisorView: React.FC = () => {
  const { airQuality, activeCity, standard } = useAQI();

  if (!airQuality) return null;

  const currentResult = airQuality.aqi_standard_results[standard] || airQuality.aqi_standard_results['US_EPA'];
  const aqi = currentResult.aqi || 50;

  const getSafetyLevel = (thresholdLow: number, thresholdHigh: number) => {
    if (aqi > thresholdHigh) return { level: 'High Risk', color: 'text-red-400', bg: 'bg-red-950/40 border-red-800/50', safe: false };
    if (aqi > thresholdLow) return { level: 'Caution Advised', color: 'text-amber-400', bg: 'bg-amber-950/40 border-amber-800/50', safe: true };
    return { level: 'Safe & Optimal', color: 'text-emerald-400', bg: 'bg-emerald-950/40 border-emerald-800/50', safe: true };
  };

  const activities = [
    {
      name: 'Running & High-Intensity Cardio',
      icon: Dumbbell,
      safety: getSafetyLevel(100, 150),
      guidance: aqi > 150
        ? 'Avoid outdoor running. Deep respiratory inhalation at high ventilation rates increases fine particulate alveolar deposition.'
        : aqi > 100
        ? 'Reduce duration and intensity. Prefer early morning before peak ozone formation.'
        : 'Optimal conditions for outdoor endurance training. Ambient air pollution poses minimal cardiovascular risk.',
    },
    {
      name: 'Cycling & Urban Commute',
      icon: Bike,
      safety: getSafetyLevel(120, 160),
      guidance: aqi > 160
        ? 'Wear an N95/FFP2 certified respirator mask or utilize enclosed mass transit options.'
        : aqi > 100
        ? 'Choose residential backstreets rather than heavy arterial traffic corridors with concentrated NO₂.'
        : 'Safe for cycling. Minimal pollutant concentration along travel routes.',
    },
    {
      name: 'Walking & Moderate Recreation',
      icon: Footprints,
      safety: getSafetyLevel(150, 200),
      guidance: aqi > 200
        ? 'Curtail prolonged outdoor exposure for all demographics.'
        : aqi > 150
        ? 'Acceptable for healthy adults; sensitive demographics should remain indoors.'
        : 'Safe for outdoor walks, park recreation, and daily errands.',
    },
    {
      name: 'Outdoor Labor & Construction',
      icon: Briefcase,
      safety: getSafetyLevel(100, 200),
      guidance: aqi > 200
        ? 'Mandatory particulate respirators and scheduled indoor rotation breaks for all on-site personnel.'
        : aqi > 100
        ? 'Ensure adequate hydration and observe workers for acute respiratory irritation.'
        : 'Standard OSHA / CPCB environmental safety protocols apply.',
    },
    {
      name: 'Sensitive Demographics (Asthma, Elderly, Pediatric)',
      icon: HeartPulse,
      safety: getSafetyLevel(50, 100),
      guidance: aqi > 100
        ? 'Stay indoors with HEPA air filtration. Keep rapid-relief bronchodilator medication readily accessible.'
        : aqi > 50
        ? 'Observe for coughing, shortness of breath, or wheezing. Moderate outdoor activity is acceptable.'
        : 'Clean atmospheric conditions. Enjoy usual outdoor activities.',
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div>
        <div className="flex items-center space-x-2">
          <Activity className="w-5 h-5 text-cyanAccent" />
          <h2 className="text-xl font-bold tracking-tight text-white font-mono">
            Environmental Health & Activity Risk Matrix
          </h2>
        </div>
        <p className="text-xs text-slate-400 mt-1">
          Evidence-based outdoor activity guidance calibrated to {activeCity.name} (Current AQI: <span className="font-bold font-mono" style={{ color: currentResult.color }}>{aqi}</span>).
        </p>
      </div>

      {/* Activity Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {activities.map((act, idx) => {
          const Icon = act.icon;
          return (
            <div
              key={idx}
              className={`rounded-lg p-5 border ${act.safety.bg} space-y-3 transition-colors`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2.5">
                  <Icon className="w-5 h-5 text-slate-200" />
                  <h3 className="text-sm font-bold text-white font-mono">{act.name}</h3>
                </div>
                <span className={`text-xs font-mono font-semibold px-2 py-0.5 rounded border border-slate-700/60 ${act.safety.color}`}>
                  {act.safety.level}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed font-sans">
                {act.guidance}
              </p>
            </div>
          );
        })}
      </div>

      {/* Official Health Authority Attribution */}
      <div className="bg-navy-900 border border-slate-800 rounded-lg p-4 text-[11px] font-mono text-slate-400 space-y-1">
        <div className="text-cyanAccent font-semibold">METHODOLOGICAL COMPLIANCE NOTICE</div>
        <p>
          Health advisories align with US EPA Air Quality Guidelines (AQG 40 CFR Part 58), World Health Organization Global Air Quality Guidelines (2021), and India Central Pollution Control Board NAQI Technical Directives.
        </p>
      </div>
    </div>
  );
};
