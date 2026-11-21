import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { AlertRule, AlertEvent } from '../../types/user';
import { BellRing, Plus, Trash2, CheckCircle2, AlertTriangle, ShieldAlert } from 'lucide-react';

export const AlertsView: React.FC = () => {
  const { user, openAuthModal } = useAuth();
  const { activeCity } = useAQI();
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [showAddModal, setShowAddModal] = useState<boolean>(false);

  // Form state
  const [locationName, setLocationName] = useState(activeCity.name);
  const [threshold, setThreshold] = useState<number>(100);
  const [pollutant, setPollutant] = useState<string>('aqi');
  const [severity, setSeverity] = useState<string>('warning');

  const loadAlerts = async () => {
    if (!user) return;
    setLoading(true);
    try {
      const [rList, eList] = await Promise.all([
        api.getAlertRules(),
        api.getAlertEvents(),
      ]);
      setRules(rList);
      setEvents(eList);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlerts();
  }, [user]);

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createAlertRule({
        location_name: locationName,
        latitude: activeCity.latitude,
        longitude: activeCity.longitude,
        threshold_aqi: threshold,
        pollutant,
        severity,
      });
      setShowAddModal(false);
      loadAlerts();
    } catch (err: any) {
      alert(err.message || 'Failed to create rule');
    }
  };

  const handleDeleteRule = async (id: string) => {
    await api.deleteAlertRule(id);
    setRules(rules.filter((r) => r.id !== id));
  };

  if (!user) {
    return (
      <div className="card-metric rounded-lg p-10 terminal-border max-w-xl mx-auto text-center space-y-4 my-12">
        <BellRing className="w-10 h-10 text-cyanAccent mx-auto" />
        <h3 className="text-lg font-bold text-white font-mono">Authentication Required for Alerts</h3>
        <p className="text-xs text-slate-300">
          Sign in or register an analyst account to configure real-time pollution threshold alerts and spike notifications.
        </p>
        <button
          onClick={openAuthModal}
          className="px-5 py-2 bg-cyanAccent text-navy-950 font-bold text-xs rounded-md hover:bg-cyan-300 transition-colors"
        >
          Sign In / Create Account
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <BellRing className="w-5 h-5 text-cyanAccent" />
            <h2 className="text-xl font-bold tracking-tight text-white font-mono">
              Intelligent Pollution Alert Rules & Spike Monitor
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Configured notification thresholds and automated particulate surge detection.
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="px-3.5 py-1.5 bg-cyanAccent text-navy-950 font-semibold text-xs rounded-md hover:bg-cyan-300 transition-colors flex items-center space-x-1.5"
        >
          <Plus className="w-4 h-4" />
          <span>New Alert Rule</span>
        </button>
      </div>

      {/* Rules List */}
      <div className="card-metric rounded-lg p-5 terminal-border space-y-3">
        <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-bold">
          Active Monitoring Rules ({rules.length})
        </h3>

        {rules.length === 0 ? (
          <p className="text-xs text-slate-500 font-mono py-4 text-center">
            No active alert rules configured. Click "New Alert Rule" above to establish a threshold.
          </p>
        ) : (
          <div className="space-y-2">
            {rules.map((rule) => (
              <div
                key={rule.id}
                className="bg-navy-950 border border-slate-800 rounded p-3 flex items-center justify-between text-xs font-mono"
              >
                <div>
                  <span className="font-bold text-white text-sm">{rule.location_name}</span>
                  <div className="text-slate-400 text-[11px] mt-0.5">
                    Trigger when <span className="text-cyanAccent">{rule.pollutant.toUpperCase()}</span> exceeds{' '}
                    <span className="text-amber-400 font-bold">{rule.threshold_aqi}</span> (Severity: {rule.severity})
                  </div>
                </div>

                <button
                  onClick={() => handleDeleteRule(rule.id)}
                  className="text-slate-500 hover:text-red-400 p-1.5"
                  title="Delete rule"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Triggered Events History */}
      <div className="card-metric rounded-lg p-5 terminal-border space-y-3">
        <h3 className="text-xs font-mono uppercase tracking-wider text-slate-300 font-bold">
          Alert Event Log ({events.length})
        </h3>
        {events.length === 0 ? (
          <p className="text-xs text-slate-500 font-mono py-4 text-center">
            No threshold breach events recorded. Atmospheric conditions have remained within parameters.
          </p>
        ) : (
          <div className="space-y-2">
            {events.map((ev) => (
              <div
                key={ev.id}
                className="bg-navy-950 border border-slate-800 rounded p-3 flex items-center justify-between text-xs font-mono"
              >
                <div className="flex items-center space-x-2.5">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <div>
                    <span className="font-semibold text-slate-200">{ev.message}</span>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      {new Date(ev.triggered_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Rule Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-navy-900 border border-slate-700 rounded-lg max-w-md w-full p-5 space-y-4">
            <h3 className="text-base font-bold text-white font-mono">Create Environmental Alert Rule</h3>
            <form onSubmit={handleCreateRule} className="space-y-3 text-xs font-mono">
              <div>
                <label className="text-slate-400 block mb-1">Target Location</label>
                <input
                  type="text"
                  value={locationName}
                  onChange={(e) => setLocationName(e.target.value)}
                  className="w-full bg-navy-950 border border-slate-700 rounded p-2 text-slate-200"
                  required
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Target Parameter</label>
                <select
                  value={pollutant}
                  onChange={(e) => setPollutant(e.target.value)}
                  className="w-full bg-navy-950 border border-slate-700 rounded p-2 text-slate-200"
                >
                  <option value="aqi">Overall AQI</option>
                  <option value="pm25">PM2.5 (Fine Particulate)</option>
                  <option value="pm10">PM10 (Coarse Particulate)</option>
                  <option value="o3">Ozone (O₃)</option>
                </select>
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Threshold Value</label>
                <input
                  type="number"
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                  className="w-full bg-navy-950 border border-slate-700 rounded p-2 text-slate-200"
                  required
                />
              </div>

              <div>
                <label className="text-slate-400 block mb-1">Severity Classification</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  className="w-full bg-navy-950 border border-slate-700 rounded p-2 text-slate-200"
                >
                  <option value="advisory">Advisory</option>
                  <option value="warning">Warning</option>
                  <option value="critical">Critical</option>
                </select>
              </div>

              <div className="flex justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 bg-navy-950 text-slate-400 hover:text-white rounded border border-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-cyanAccent text-navy-950 font-bold rounded"
                >
                  Save Rule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
