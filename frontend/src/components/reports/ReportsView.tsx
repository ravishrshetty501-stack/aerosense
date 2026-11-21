import React, { useState, useEffect } from 'react';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { FileText, Download, Calendar, CheckCircle2, ShieldCheck, RefreshCw } from 'lucide-react';

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
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <FileText className="w-5 h-5 text-cyanAccent" />
            <h2 className="text-xl font-bold tracking-tight text-white font-mono">
              Environmental Intelligence Reports & PDF Export
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Generate verifiable compliance and intelligence reports with data attribution and official standard methodologies.
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center space-x-2">
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="bg-navy-950 border border-slate-700 rounded-md px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyanAccent"
          >
            <option value="Daily Summary">Daily Summary</option>
            <option value="Weekly Reanalysis">Weekly Reanalysis</option>
          </select>

          <button
            onClick={handleDownloadPdf}
            className="px-4 py-1.5 bg-cyanAccent text-navy-950 font-semibold text-xs rounded-md hover:bg-cyan-300 transition-colors flex items-center space-x-1.5 shadow-lg shadow-cyanAccent/20"
          >
            <Download className="w-4 h-4" />
            <span>Export Official PDF</span>
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="w-6 h-6 text-cyanAccent animate-spin" />
          <span className="ml-2 text-xs font-mono text-slate-400">Compiling environmental report for {activeCity.name}...</span>
        </div>
      )}

      {!loading && reportData && (
        <div className="card-metric rounded-lg p-6 terminal-border space-y-6">
          {/* Document Header */}
          <div className="border-b border-slate-800 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-cyanAccent">
                AEROSENSE COMPLIANCE BRIEFING
              </span>
              <h3 className="text-2xl font-bold text-white font-mono mt-0.5">
                {reportData.city}
              </h3>
              <p className="text-xs text-slate-400 font-mono">
                Period: {reportData.period} • Generated: {reportData.generated_at}
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs font-mono text-slate-400 block">Calculated AQI ({standard})</span>
              <span className="text-3xl font-bold font-mono text-cyanAccent">
                {reportData.aqi_value}
              </span>
              <span className="text-xs font-semibold text-slate-300 block">{reportData.aqi_category}</span>
            </div>
          </div>

          {/* Pollutant Observations Table */}
          <div className="space-y-2">
            <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400">
              Verified Pollutant Concentration Matrix
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono border border-slate-800 rounded">
                <thead className="bg-navy-950 border-b border-slate-800 text-slate-400">
                  <tr>
                    <th className="p-2.5">Pollutant</th>
                    <th className="p-2.5">Concentration</th>
                    <th className="p-2.5">Unit</th>
                    <th className="p-2.5">Observation Type</th>
                    <th className="p-2.5">Source Attribution</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-slate-300">
                  {Object.entries(reportData.measurements || {}).map(([p, m]: [string, any]) => (
                    <tr key={p} className="hover:bg-navy-900/50">
                      <td className="p-2.5 font-bold text-cyanAccent">{p.toUpperCase()}</td>
                      <td className="p-2.5 font-semibold text-white">{m.value !== null ? m.value : '—'}</td>
                      <td className="p-2.5 text-slate-400">{m.unit}</td>
                      <td className="p-2.5">
                        <span className="px-1.5 py-0.5 bg-navy-950 rounded text-[10px] border border-slate-800">
                          {m.type}
                        </span>
                      </td>
                      <td className="p-2.5 text-slate-400 truncate max-w-xs">{m.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Health & Public Advisory */}
          <div className="bg-navy-950/70 border border-slate-800 rounded p-4 space-y-1.5">
            <h5 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-semibold">
              Advisory Summary
            </h5>
            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              {reportData.health_advisory}
            </p>
          </div>

          {/* Report Footer / Signature */}
          <div className="pt-4 border-t border-slate-800 flex items-center justify-between text-[11px] font-mono text-slate-500">
            <span>Primary Provider: {reportData.primary_source}</span>
            <span className="flex items-center text-emerald-400">
              <ShieldCheck className="w-3.5 h-3.5 mr-1" />
              Cryptographically Verified Report
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
