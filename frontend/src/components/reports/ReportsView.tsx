import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { AQIStandard, ReportDataResponse, ReportMeasurementItem } from '../../types/airQuality';
import { getStandardAqiScaleColor } from '../../utils/airQualityHelpers';
import { FileText, Download, RefreshCw, AlertTriangle } from 'lucide-react';

function isFiniteNumber(val: unknown): val is number {
  return typeof val === 'number' && Number.isFinite(val);
}

function normalizeFiniteNumber(val: number): number {
  return Object.is(val, -0) ? 0 : val;
}

export function formatReportConcentration(val: unknown): string {
  if (!isFiniteNumber(val)) return 'Unavailable';
  return String(normalizeFiniteNumber(val));
}

export interface ResolvedReportDisplay {
  hasFiniteAqi: boolean;
  aqiDisplay: number | string;
  aqiColor: string;
  aqiCategory: string;
  dominantPollutant: string;
  primarySource: string;
  ingestionMode: string;
  validationStatus: string;
  healthAdvisory: string;
  measurementEntries: Array<[string, ReportMeasurementItem]>;
}

/**
 * Resolves report metrics, category styling, and telemetry attribution without fabricating
 * pollutants, AQI values, or ingestion claims when data is missing or non-finite.
 */
export function resolveReportDisplay(reportData: ReportDataResponse): ResolvedReportDisplay {
  const hasFiniteAqi = isFiniteNumber(reportData.aqi_value);
  const aqiDisplay = hasFiniteAqi ? normalizeFiniteNumber(reportData.aqi_value as number) : '—';
  const aqiColor = hasFiniteAqi
    ? getStandardAqiScaleColor(reportData.aqi_value, reportData.aqi_standard)
    : '#647570';
  const aqiCategory = reportData.aqi_category?.trim() ? reportData.aqi_category : 'Unavailable';
  const dominantPollutant = reportData.dominant_pollutant?.trim()
    ? reportData.dominant_pollutant
    : 'Unavailable';
  const primarySource = reportData.primary_source?.trim() ? reportData.primary_source : 'Unavailable';

  const measurementEntries = Object.entries(reportData.measurements || {}) as Array<
    [string, ReportMeasurementItem]
  >;
  const validMeasurements = measurementEntries.filter(([, item]) => isFiniteNumber(item?.value));
  const hasValidTelemetry = validMeasurements.length > 0 || hasFiniteAqi;
  const hasGroundMeasurement = validMeasurements.some(
    ([, item]) => item?.type === 'ground_observation'
  );

  let ingestionMode = 'Unavailable';
  if (hasValidTelemetry) {
    ingestionMode =
      hasGroundMeasurement || (validMeasurements.length > 0 && reportData.is_ground_observation)
        ? 'Ground Telemetry'
        : reportData.is_ground_observation
        ? 'Ground Telemetry'
        : 'Model Estimate';
  }

  return {
    hasFiniteAqi,
    aqiDisplay,
    aqiColor,
    aqiCategory,
    dominantPollutant,
    primarySource,
    ingestionMode,
    validationStatus: hasValidTelemetry ? 'Quality Checked' : 'Data Unavailable',
    healthAdvisory: reportData.health_advisory?.trim()
      ? reportData.health_advisory
      : 'No public health advisory available for this reporting period.',
    measurementEntries,
  };
}

/**
 * Fetches briefing data and returns a normalized outcome with explicit error state on failure.
 */
export async function loadReportBriefing(
  city: string,
  period: string,
  standard: AQIStandard,
  fetcher: (c: string, p: string, s: AQIStandard) => Promise<ReportDataResponse> = (c, p, s) =>
    api.getReportData(c, p, s)
): Promise<{ data: ReportDataResponse | null; error: string | null }> {
  try {
    const data = await fetcher(city, period, standard);
    return { data, error: null };
  } catch (err: unknown) {
    const msg =
      err instanceof Error && err.message
        ? err.message
        : 'Failed to compile environmental intelligence report.';
    return { data: null, error: msg };
  }
}

export function openReportPdf(
  url: string,
  openWindow: (url: string, target?: string, features?: string) => unknown = (u, target, features) =>
    window.open(u, target, features)
): { opened: boolean; error: string | null } {
  const cleanUrl = typeof url === 'string' ? url.trim() : '';
  if (!cleanUrl || (!cleanUrl.startsWith('/') && !/^https?:\/\//i.test(cleanUrl))) {
    return { opened: false, error: 'Unable to export PDF: report download URL is missing or invalid.' };
  }
  try {
    const result = openWindow(cleanUrl, '_blank', 'noopener,noreferrer');
    if (result === false) {
      return { opened: false, error: 'Unable to open PDF export window.' };
    }
    return { opened: true, error: null };
  } catch {
    return { opened: false, error: 'Failed to launch PDF export download.' };
  }
}

export const ReportsView: React.FC = () => {
  const { activeCity, standard } = useAQI();
  const [period, setPeriod] = useState<string>('Daily Summary');
  const [reportData, setReportData] = useState<ReportDataResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const latestRequestIdRef = useRef<number>(0);

  const fetchReport = useCallback(
    async (isCancelled: () => boolean = () => false) => {
      const requestId = ++latestRequestIdRef.current;
      setLoading(true);
      setLoadError(null);
      setReportData(null);
      setExportError(null);
      const outcome = await loadReportBriefing(activeCity.name, period, standard);
      if (isCancelled() || latestRequestIdRef.current !== requestId) return;
      setReportData(outcome.data);
      setLoadError(outcome.error);
      setLoading(false);
    },
    [activeCity.name, period, standard]
  );

  useEffect(() => {
    let cancelled = false;
    fetchReport(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [fetchReport]);

  const handleDownloadPdf = () => {
    const url = api.getReportPdfUrl(activeCity.name, period, standard);
    const outcome = openReportPdf(url);
    setExportError(outcome.error);
  };

  const resolved = reportData ? resolveReportDisplay(reportData) : null;

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-clima-border dark:border-darkClima-border pb-5">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-clima-subtle dark:bg-darkClima-subtle rounded-lg text-clima-accent dark:text-darkClima-accent border border-clima-border dark:border-darkClima-border">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-clima-text dark:text-darkClima-text tracking-tight font-sans">
                Environmental Intelligence Reports & PDF Export
              </h2>
              <p className="text-xs text-clima-muted dark:text-darkClima-muted mt-0.5">
                Generate and download compliance and analytical briefings with verified ground sensor telemetry and official regulatory methodologies.
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-2.5">
          <select
            aria-label="Reporting Interval"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="bg-clima-surface dark:bg-darkClima-surface border border-clima-border dark:border-darkClima-border rounded-lg px-3 py-1.5 text-xs text-clima-text dark:text-darkClima-text focus:outline-none focus:border-clima-accent dark:focus:border-darkClima-accent font-sans"
          >
            <option value="Daily Summary">Daily Summary</option>
            <option value="Weekly Reanalysis">Weekly Reanalysis</option>
          </select>

          <button
            onClick={handleDownloadPdf}
            className="px-4 py-1.5 bg-clima-accent dark:bg-darkClima-accent hover:opacity-90 text-white dark:text-darkClima-bg font-medium text-xs rounded-lg transition-colors flex items-center space-x-1.5 shadow-sm"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Official PDF</span>
          </button>
        </div>
      </div>

      {exportError && (
        <div
          role="alert"
          className="p-3.5 bg-red-500/10 border border-red-500/30 rounded-xl flex items-center space-x-2.5 text-xs text-red-700 dark:text-red-300"
        >
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{exportError}</span>
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center p-16">
          <RefreshCw className="w-6 h-6 text-clima-accent dark:text-darkClima-accent animate-spin" />
          <span className="ml-3 text-xs text-clima-muted dark:text-darkClima-muted font-sans">
            Compiling environmental intelligence report for {activeCity.name}...
          </span>
        </div>
      )}

      {!loading && loadError && (
        <div
          role="alert"
          className="p-5 bg-red-500/10 border border-red-500/30 rounded-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs text-red-700 dark:text-red-300"
        >
          <div className="flex items-center space-x-2.5">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{loadError}</span>
          </div>
          <button
            type="button"
            onClick={() => fetchReport()}
            className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 rounded-lg font-medium transition-colors self-start sm:self-auto"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !loadError && reportData && resolved && (
        <div className="bg-clima-surface dark:bg-darkClima-surface rounded-xl p-6 border border-clima-border dark:border-darkClima-border space-y-6 shadow-floating dark:shadow-floating-dark">
          {/* Document Header */}
          <div className="border-b border-clima-border dark:border-darkClima-border pb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <span className="text-[10px] uppercase tracking-widest text-clima-accent dark:text-darkClima-accent font-mono font-semibold">
                Official Compliance Briefing
              </span>
              <h3 className="text-2xl font-bold text-clima-text dark:text-darkClima-text mt-0.5 font-sans">
                {reportData.city}
              </h3>
              <p className="text-xs text-clima-muted dark:text-darkClima-muted font-sans mt-0.5">
                Reporting Interval: <span className="text-clima-text dark:text-darkClima-text font-medium">{reportData.period}</span> • Generated: {reportData.generated_at || 'Unavailable'}
              </p>
            </div>
            <div className="sm:text-right">
              <span className="text-xs text-clima-muted dark:text-darkClima-muted block font-sans">Standard Index ({standard.replace('_', ' ')})</span>
              <span
                className="text-3xl font-extrabold font-mono"
                style={{ color: resolved.aqiColor }}
              >
                {resolved.aqiDisplay}
              </span>
              <span className="text-xs font-semibold text-clima-text dark:text-darkClima-text block font-sans">{resolved.aqiCategory}</span>
            </div>
          </div>

          {/* Quick Stats Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-clima-subtle/80 dark:bg-darkClima-subtle/80 p-4 rounded-xl border border-clima-border dark:border-darkClima-border text-xs">
            <div>
              <span className="text-[10px] text-clima-muted dark:text-darkClima-muted font-sans block">Dominant Pollutant</span>
              <span className="font-mono font-bold text-clima-text dark:text-darkClima-text text-sm mt-0.5 block">{resolved.dominantPollutant}</span>
            </div>
            <div>
              <span className="text-[10px] text-clima-muted dark:text-darkClima-muted font-sans block">Primary Data Source</span>
              <span className="font-sans text-clima-text dark:text-darkClima-text font-medium text-xs mt-0.5 block truncate" title={resolved.primarySource}>{resolved.primarySource}</span>
            </div>
            <div>
              <span className="text-[10px] text-clima-muted dark:text-darkClima-muted font-sans block">Ingestion Mode</span>
              <span
                className={`font-semibold text-xs mt-0.5 block font-sans ${
                  resolved.ingestionMode === 'Unavailable'
                    ? 'text-clima-muted dark:text-darkClima-muted'
                    : 'text-[#0f6848] dark:text-[#4BBF87]'
                }`}
              >
                {resolved.ingestionMode}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-clima-muted dark:text-darkClima-muted font-sans block">Validation Status</span>
              <span className="font-sans text-clima-secondary dark:text-darkClima-secondary font-semibold text-xs mt-0.5 block">
                {resolved.validationStatus}
              </span>
            </div>
          </div>

          {/* Pollutant Observations Table */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-clima-text dark:text-darkClima-text font-sans">
              Monitored Concentration Matrix
            </h4>
            <div className="overflow-x-auto rounded-lg border border-clima-border dark:border-darkClima-border">
              <table className="w-full text-left text-xs">
                <thead className="bg-clima-subtle dark:bg-darkClima-subtle text-clima-muted dark:text-darkClima-muted font-mono text-[11px] border-b border-clima-border dark:border-darkClima-border">
                  <tr>
                    <th className="px-4 py-2.5">Parameter</th>
                    <th className="px-4 py-2.5">Concentration</th>
                    <th className="px-4 py-2.5">Unit</th>
                    <th className="px-4 py-2.5">Type</th>
                    <th className="px-4 py-2.5">Source Attribution</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-clima-border/80 dark:divide-darkClima-border/80 font-sans">
                  {resolved.measurementEntries.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-4 text-center text-clima-muted dark:text-darkClima-muted">
                        No pollutant measurements available for this briefing.
                      </td>
                    </tr>
                  ) : (
                    resolved.measurementEntries.map(([key, val]) => (
                      <tr key={key} className="hover:bg-clima-subtle/40 dark:hover:bg-darkClima-subtle/40">
                        <td className="px-4 py-2.5 font-bold font-mono text-clima-accent dark:text-darkClima-accent uppercase">{key}</td>
                        <td className="px-4 py-2.5 font-mono text-clima-text dark:text-darkClima-text font-semibold">
                          {formatReportConcentration(val?.value)}
                        </td>
                        <td className="px-4 py-2.5 font-mono text-clima-muted dark:text-darkClima-muted">{val?.unit || '—'}</td>
                        <td className="px-4 py-2.5 text-clima-text dark:text-darkClima-text">
                          <span className="px-1.5 py-0.5 rounded bg-clima-subtle dark:bg-darkClima-subtle text-[10px] font-mono border border-clima-border dark:border-darkClima-border">
                            {val?.type || 'Unavailable'}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-clima-muted dark:text-darkClima-muted truncate max-w-xs">{val?.source || 'Unavailable'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Health Advisory Section */}
          <div className="bg-clima-subtle/60 dark:bg-darkClima-subtle/60 p-4 rounded-xl border border-clima-border dark:border-darkClima-border space-y-1.5">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-clima-text dark:text-darkClima-text font-sans">
              Public Health Advisory Summary
            </h4>
            <p className="text-xs text-clima-muted dark:text-darkClima-muted leading-relaxed font-sans">{resolved.healthAdvisory}</p>
          </div>
        </div>
      )}
    </div>
  );
};
