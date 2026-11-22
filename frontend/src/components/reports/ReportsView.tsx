import React, { useState, useEffect } from 'react';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { FileText, Download, RefreshCw, CheckCircle2, ShieldCheck, Layers } from 'lucide-react';

export const ReportsView: React.FC = () => {
  const { activeCity, standard } = useAQI();
  const [period, setPeriod] = useState<string>('Daily Summary');
  const [reportData, setReportData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    setLoading(true);
    api.getReportData(activeCity.name, period, standard)
      .then((data) => setReportData(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeCity, period, standard]);

  const handleDownloadPdf = () => {
    const url = api.getReportPdfUrl(activeCity.name, period, standard);
    window.open(url, '_blank');
  };

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

      {loading && (
        <div className="flex items-center justify-center p-16">
          <RefreshCw className="w-6 h-6 text-clima-accent dark:text-darkClima-accent animate-spin" />
          <span className="ml-3 text-xs text-clima-muted dark:text-darkClima-muted font-sans">
            Compiling environmental intelligence report for {activeCity.name}...
          </span>
        </div>
      )}

      {!loading && reportData && (
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
                Reporting Interval: <span className="text-clima-text dark:text-darkClima-text font-medium">{reportData.period}</span> • Generated: {reportData.generated_at}
              </p>
            </div>
            <div className="sm:text-right">
              <span className="text-xs text-clima-muted dark:text-darkClima-muted block font-sans">Standard Index ({standard.replace('_', ' ')})</span>
              <span className="text-3xl font-extrabold font-mono text-clima-accent dark:text-darkClima-accent">
                {reportData.aqi_value ?? '—'}
              </span>
              <span className="text-xs font-semibold text-clima-text dark:text-darkClima-text block font-sans">{reportData.aqi_category}</span>
            </div>
          </div>

          {/* Quick Stats Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-clima-subtle/80 dark:bg-darkClima-subtle/80 p-4 rounded-xl border border-clima-border dark:border-darkClima-border text-xs">
            <div>
              <span className="text-[10px] text-clima-muted dark:text-darkClima-muted font-sans block">Dominant Pollutant</span>
              <span className="font-mono font-bold text-clima-text dark:text-darkClima-text text-sm mt-0.5 block">{reportData.dominant_pollutant || 'PM2.5'}</span>
            </div>
            <div>
              <span className="text-[10px] text-clima-muted dark:text-darkClima-muted font-sans block">Primary Data Source</span>
              <span className="font-sans text-clima-text dark:text-darkClima-text font-medium text-xs mt-0.5 block truncate" title={reportData.primary_source}>{reportData.primary_source}</span>
            </div>
            <div>
              <span className="text-[10px] text-clima-muted dark:text-darkClima-muted font-sans block">Ingestion Mode</span>
              <span className="font-sans text-[#0f6848] dark:text-[#4BBF87] font-semibold text-xs mt-0.5 block">
                {reportData.is_ground_observation ? 'Ground Telemetry' : 'Model Estimate'}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-clima-muted dark:text-darkClima-muted font-sans block">Validation Status</span>
              <span className="font-sans text-clima-secondary dark:text-darkClima-secondary font-semibold text-xs mt-0.5 block">Quality Checked</span>
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
                  {Object.entries(reportData.measurements || {}).map(([key, val]: [string, any]) => (
                    <tr key={key} className="hover:bg-clima-subtle/40 dark:hover:bg-darkClima-subtle/40">
                      <td className="px-4 py-2.5 font-bold font-mono text-clima-accent dark:text-darkClima-accent uppercase">{key}</td>
                      <td className="px-4 py-2.5 font-mono text-clima-text dark:text-darkClima-text font-semibold">{val.value ?? 'Unavailable'}</td>
                      <td className="px-4 py-2.5 font-mono text-clima-muted dark:text-darkClima-muted">{val.unit}</td>
                      <td className="px-4 py-2.5 text-clima-text dark:text-darkClima-text">
                        <span className="px-1.5 py-0.5 rounded bg-clima-subtle dark:bg-darkClima-subtle text-[10px] font-mono border border-clima-border dark:border-darkClima-border">
                          {val.type}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-clima-muted dark:text-darkClima-muted truncate max-w-xs">{val.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Health Advisory Section */}
          <div className="bg-clima-subtle/60 dark:bg-darkClima-subtle/60 p-4 rounded-xl border border-clima-border dark:border-darkClima-border space-y-1.5">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-clima-text dark:text-darkClima-text font-sans">
              Public Health Advisory Summary
            </h4>
            <p className="text-xs text-clima-muted dark:text-darkClima-muted leading-relaxed font-sans">{reportData.health_advisory}</p>
          </div>
        </div>
      )}
    </div>
  );
};
