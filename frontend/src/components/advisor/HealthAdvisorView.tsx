import React, { useState } from 'react';
import { useAQI } from '../../context/AQIContext';
import {
  Activity,
  Footprints,
  Bike,
  Dumbbell,
  Briefcase,
  HeartPulse,
  Info,
  Home,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck
} from 'lucide-react';

export const HealthAdvisorView: React.FC = () => {
  const { airQuality, activeCity, standard } = useAQI();
  const [selectedActivityKey, setSelectedActivityKey] = useState<string>('all');

  if (!airQuality) return null;

  const currentResult = airQuality.aqi_standard_results[standard] || airQuality.aqi_standard_results['US_EPA'];
  const aqi = currentResult.aqi || 50;
  const dominant = airQuality.dominant_pollutant || 'PM2.5';

  const getSafetyLevel = (thresholdLow: number, thresholdHigh: number) => {
    if (aqi > thresholdHigh) {
      return {
        level: 'High Risk',
        color: '#C94E55',
        badge: 'bg-[#C94E55]/15 text-[#C94E55] border-[#C94E55]/30',
        safe: false,
      };
    }
    if (aqi > thresholdLow) {
      return {
        level: 'Caution Advised',
        color: '#D5A33A',
        badge: 'bg-[#D5A33A]/15 text-[#D5A33A] border-[#D5A33A]/30',
        safe: true,
      };
    }
    return {
      level: 'Safe & Optimal',
      color: '#23966B',
      badge: 'bg-[#23966B]/15 text-[#23966B] border-[#23966B]/30',
      safe: true,
    };
  };

  const activities = [
    {
      id: 'running',
      name: 'Running & Cardiovascular Workouts',
      icon: Dumbbell,
      safety: getSafetyLevel(100, 150),
      guidance:
        aqi > 150
          ? 'Suspend intense outdoor running. High ventilation rates increase fine particulate deposition deep into alveolar lung tissues.'
          : aqi > 100
          ? 'Curtail duration and intensity. Schedule workouts in early morning before peak ozone and traffic-related NO₂.'
          : 'Ideal conditions for outdoor cardiovascular training. Ambient particulate exposure poses minimal risk to pulmonary health.',
    },
    {
      id: 'cycling',
      name: 'Cycling & Active Urban Commute',
      icon: Bike,
      safety: getSafetyLevel(120, 160),
      guidance:
        aqi > 160
          ? 'Wear a certified N95 / FFP2 respirator with tight facial seal, or use climate-controlled mass transit.'
          : aqi > 100
          ? 'Choose designated low-traffic bike corridors or residential side streets to avoid concentrated tailpipe exhaust.'
          : 'Safe for cycling and urban commuting with normal precautions.',
    },
    {
      id: 'walking',
      name: 'Walking & Moderate Recreation',
      icon: Footprints,
      safety: getSafetyLevel(150, 200),
      guidance:
        aqi > 200
          ? 'Limit non-essential outdoor walking for all populations. Keep doors and windows closed.'
          : aqi > 150
          ? 'Acceptable for healthy individuals; vulnerable demographics should limit outdoor exposure.'
          : 'Safe for walking, park recreation, and daily errands.',
    },
    {
      id: 'labor',
      name: 'Outdoor Labor & Construction',
      icon: Briefcase,
      safety: getSafetyLevel(100, 200),
      guidance:
        aqi > 200
          ? 'Mandatory particulate respirators and scheduled indoor rotation breaks for all on-site personnel.'
          : aqi > 100
          ? 'Provide adequate hydration and monitor workers for acute respiratory irritation or eye fatigue.'
          : 'Standard workplace health and safety protocols apply.',
    },
    {
      id: 'sensitive',
      name: 'Sensitive Demographics (Asthma, Elderly, Pediatric)',
      icon: HeartPulse,
      safety: getSafetyLevel(50, 100),
      guidance:
        aqi > 100
          ? 'Remain indoors with clean air filtration. Keep rapid-relief bronchodilator medication readily accessible.'
          : aqi > 50
          ? 'Noticeable symptoms like coughing or wheezing may emerge during prolonged exertion. Plan regular rest intervals.'
          : 'Clean atmospheric conditions. Standard daily outdoor activities are encouraged.',
    },
  ];

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
                <span className="font-mono font-bold text-clima-text dark:text-darkClima-text underline decoration-2" style={{ textDecorationColor: currentResult.color }}>
                  {aqi}
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
          backgroundColor: `${currentResult.color}10`,
          borderColor: `${currentResult.color}35`,
        }}
      >
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span
              className="text-xs font-bold uppercase tracking-wider font-mono px-2 py-0.5 rounded"
              style={{ backgroundColor: `${currentResult.color}25`, color: currentResult.color }}
            >
              {currentResult.category}
            </span>
            <span className="text-xs text-clima-muted dark:text-darkClima-muted">Official Health Advisory</span>
          </div>
          <p className="text-sm font-medium text-clima-text dark:text-darkClima-text">{currentResult.advisory}</p>
        </div>

        <div className="shrink-0 flex items-center space-x-4">
          <div className="text-right">
            <span className="text-[10px] text-clima-muted dark:text-darkClima-muted uppercase tracking-widest block font-mono">Index</span>
            <span className="text-3xl font-extrabold font-mono" style={{ color: currentResult.color }}>
              {aqi}
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
            {aqi > 100
              ? 'Keep windows closed during peak traffic hours. Deploy True HEPA (H13/H14) air filtration units to remove fine particles down to 0.3 µm.'
              : 'Ventilate living and working spaces with fresh air during low-traffic afternoon periods to prevent indoor CO₂ buildup.'}
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
