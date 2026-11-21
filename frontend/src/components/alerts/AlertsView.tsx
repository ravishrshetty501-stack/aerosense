import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useAQI } from '../../context/AQIContext';
import { api } from '../../services/api';
import { AlertRule, AlertEvent } from '../../types/user';
import { BellRing, Plus, Trash2, CheckCircle2, AlertTriangle, ShieldAlert, X } from 'lucide-react';

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
      <div className="bg-clima-surface dark:bg-darkClima-surface rounded-xl p-10 border border-clima-border dark:border-darkClima-border max-w-xl mx-auto text-center space-y-4 my-12 shadow-floating dark:shadow-floating-dark font-sans">
        <div className="w-12 h-12 rounded-full bg-clima-accent/10 dark:bg-darkClima-accent/10 text-clima-accent dark:text-darkClima-accent flex items-center justify-center mx-auto">
          <BellRing className="w-6 h-6" />
        </div>
        <h3 className="text-lg font-bold text-clima-text dark:text-darkClima-text font-sans">Sign In to Configure Air Quality Alerts</h3>
        <p className="text-xs text-clima-muted dark:text-darkClima-muted leading-relaxed font-sans max-w-md mx-auto">
          Create threshold alerts to receive notifications whenever particulate matter (PM2.5, PM10) or overall AQI in your monitored regions breaches health safety standards.
        </p>
        <button
          onClick={openAuthModal}
          className="px-5 py-2.5 bg-clima-accent dark:bg-darkClima-accent hover:opacity-90 text-white dark:text-darkClima-bg font-medium text-xs rounded-lg transition-colors shadow-sm"
        >
          Sign In or Register
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-12 font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-clima-border dark:border-darkClima-border pb-5">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-clima-subtle dark:bg-darkClima-subtle rounded-lg text-clima-accent dark:text-darkClima-accent border border-clima-border dark:border-darkClima-border">
              <BellRing className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-clima-text dark:text-darkClima-text tracking-tight font-sans">
                Intelligent Threshold Alerts & Surveillance
              </h2>
              <p className="text-xs text-clima-muted dark:text-darkClima-muted mt-0.5">
                Automated monitors that track ambient pollutant breaches for designated cities.
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={() => {
            setLocationName(activeCity.name);
            setShowAddModal(true);
          }}
          className="px-4 py-2 bg-clima-accent dark:bg-darkClima-accent hover:opacity-90 text-white dark:text-darkClima-bg font-medium text-xs rounded-lg transition-colors flex items-center space-x-1.5 shadow-sm self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>New Alert Rule</span>
        </button>
      </div>

      {/* Rules List */}
      <div className="bg-clima-surface dark:bg-darkClima-surface rounded-xl p-5 border border-clima-border dark:border-darkClima-border space-y-4 shadow-floating dark:shadow-floating-dark">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-clima-text dark:text-darkClima-text font-sans">
          Configured Alert Rules ({rules.length})
        </h3>

        {rules.length === 0 ? (
          <p className="text-xs text-clima-muted dark:text-darkClima-muted font-sans py-4 text-center">
            No active alert rules configured yet. Click "New Alert Rule" above to create one.
          </p>
        ) : (
          <div className="space-y-2.5">
            {rules.map((rule) => (
              <div
                key={rule.id}
                className="bg-clima-subtle/80 dark:bg-darkClima-subtle/80 border border-clima-border dark:border-darkClima-border rounded-lg p-3.5 flex items-center justify-between text-xs font-sans"
              >
                <div>
                  <span className="font-bold text-clima-text dark:text-darkClima-text text-sm">{rule.location_name}</span>
                  <div className="text-clima-muted dark:text-darkClima-muted text-xs mt-0.5">
                    Trigger when <strong className="text-clima-accent dark:text-darkClima-accent uppercase font-mono">{rule.pollutant}</strong> exceeds{' '}
                    <strong className="text-[#D5A33A] font-mono">{rule.threshold_aqi}</strong> (Severity: {rule.severity})
                  </div>
                </div>

                <button
                  onClick={() => handleDeleteRule(rule.id)}
                  className="text-clima-muted dark:text-darkClima-muted hover:text-[#C94E55] p-1.5 rounded hover:bg-clima-surface dark:hover:bg-darkClima-surface transition-colors"
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
      <div className="bg-clima-surface dark:bg-darkClima-surface rounded-xl p-5 border border-clima-border dark:border-darkClima-border space-y-4 shadow-floating dark:shadow-floating-dark">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-clima-text dark:text-darkClima-text font-sans">
          Threshold Breach Event Log ({events.length})
        </h3>
        {events.length === 0 ? (
          <p className="text-xs text-clima-muted dark:text-darkClima-muted font-sans py-4 text-center">
            No threshold breach events recorded. Monitored atmospheric levels are currently within safe limits.
          </p>
        ) : (
          <div className="space-y-2.5">
            {events.map((ev) => (
              <div
                key={ev.id}
                className="bg-clima-subtle/80 dark:bg-darkClima-subtle/80 border border-clima-border dark:border-darkClima-border rounded-lg p-3.5 flex items-center justify-between text-xs font-sans"
              >
                <div className="flex items-center space-x-3">
                  <AlertTriangle className="w-4 h-4 text-[#D5A33A] shrink-0" />
                  <div>
                    <span className="font-medium text-clima-text dark:text-darkClima-text">{ev.message}</span>
                    <div className="text-[11px] text-clima-muted dark:text-darkClima-muted font-mono mt-0.5">
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
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-clima-surface dark:bg-darkClima-surface border border-clima-border dark:border-darkClima-border rounded-xl max-w-md w-full p-6 space-y-4 shadow-2xl font-sans">
            <div className="flex items-center justify-between border-b border-clima-border dark:border-darkClima-border pb-3">
              <h3 className="text-base font-bold text-clima-text dark:text-darkClima-text">Create Air Quality Alert Rule</h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateRule} className="space-y-4 text-xs font-sans">
              <div>
                <label className="text-clima-text dark:text-darkClima-text font-medium block mb-1.5">Monitored City or Region</label>
                <input
                  type="text"
                  value={locationName}
                  onChange={(e) => setLocationName(e.target.value)}
                  className="w-full bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-lg p-2.5 text-clima-text dark:text-darkClima-text focus:outline-none focus:border-clima-accent dark:focus:border-darkClima-accent"
                  required
                />
              </div>

              <div>
                <label className="text-clima-text dark:text-darkClima-text font-medium block mb-1.5">Target Parameter</label>
                <select
                  value={pollutant}
                  onChange={(e) => setPollutant(e.target.value)}
                  className="w-full bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-lg p-2.5 text-clima-text dark:text-darkClima-text focus:outline-none focus:border-clima-accent dark:focus:border-darkClima-accent"
                >
                  <option value="aqi">Overall Air Quality Index (AQI)</option>
                  <option value="pm25">PM2.5 (Fine Particulate Matter)</option>
                  <option value="pm10">PM10 (Coarse Inhalable Dust)</option>
                  <option value="o3">Ozone (O₃)</option>
                </select>
              </div>

              <div>
                <label className="text-clima-text dark:text-darkClima-text font-medium block mb-1.5">Threshold Level</label>
                <input
                  type="number"
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                  className="w-full bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-lg p-2.5 text-clima-text dark:text-darkClima-text font-mono focus:outline-none focus:border-clima-accent dark:focus:border-darkClima-accent"
                  required
                />
              </div>

              <div>
                <label className="text-clima-text dark:text-darkClima-text font-medium block mb-1.5">Alert Severity</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  className="w-full bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-lg p-2.5 text-clima-text dark:text-darkClima-text focus:outline-none focus:border-clima-accent dark:focus:border-darkClima-accent"
                >
                  <option value="advisory">Advisory (Mild concern)</option>
                  <option value="warning">Warning (Noticeable health impact)</option>
                  <option value="critical">Critical (Severe exposure hazard)</option>
                </select>
              </div>

              <div className="flex justify-end space-x-2.5 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-clima-subtle dark:bg-darkClima-subtle hover:bg-clima-border dark:hover:bg-darkClima-border text-clima-muted dark:text-darkClima-muted rounded-lg border border-clima-border dark:border-darkClima-border transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-clima-accent dark:bg-darkClima-accent hover:opacity-90 text-white dark:text-darkClima-bg font-medium rounded-lg transition-colors shadow-sm"
                >
                  Save Alert Rule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
