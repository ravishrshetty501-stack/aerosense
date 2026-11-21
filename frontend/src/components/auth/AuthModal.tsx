import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { User, Lock, Mail, X, ShieldAlert } from 'lucide-react';

export const AuthModal: React.FC = () => {
  const { isAuthModalOpen, closeAuthModal, login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!isAuthModalOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (isRegister) {
        await register(email, password, name);
      } else {
        await login(email, password);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 font-sans">
      <div className="bg-clima-surface dark:bg-darkClima-surface border border-clima-border dark:border-darkClima-border rounded-xl max-w-sm w-full p-6 relative shadow-2xl space-y-4">
        {/* Close Button */}
        <button
          onClick={closeAuthModal}
          className="absolute top-4 right-4 text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Modal Header */}
        <div className="space-y-1">
          <h3 className="text-base font-bold text-clima-text dark:text-darkClima-text font-sans">
            {isRegister ? 'Analyst Registration' : 'Analyst Authentication'}
          </h3>
          <p className="text-xs text-clima-muted dark:text-darkClima-muted">
            Access secure telemetry preferences, saved locations and alerts.
          </p>
        </div>

        {error && (
          <div className="p-2.5 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 rounded-lg flex items-center space-x-2 text-xs text-red-700 dark:text-red-300">
            <ShieldAlert className="w-4 h-4 shrink-0 text-red-500" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs font-sans">
          {isRegister && (
            <div>
              <label className="text-clima-text dark:text-darkClima-text font-medium block mb-1">Full Name</label>
              <div className="relative">
                <User className="w-3.5 h-3.5 text-clima-muted dark:text-darkClima-muted absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Dr. Jane Doe"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-lg py-2 pl-9 pr-3 text-clima-text dark:text-darkClima-text placeholder-clima-muted dark:placeholder-darkClima-muted focus:outline-none focus:border-clima-accent dark:focus:border-darkClima-accent"
                />
              </div>
            </div>
          )}

          <div>
            <label className="text-clima-text dark:text-darkClima-text font-medium block mb-1">Email Address</label>
            <div className="relative">
              <Mail className="w-3.5 h-3.5 text-clima-muted dark:text-darkClima-muted absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="email"
                placeholder="analyst@aerosense.ai"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-lg py-2 pl-9 pr-3 text-clima-text dark:text-darkClima-text placeholder-clima-muted dark:placeholder-darkClima-muted focus:outline-none focus:border-clima-accent dark:focus:border-darkClima-accent"
              />
            </div>
          </div>

          <div>
            <label className="text-clima-text dark:text-darkClima-text font-medium block mb-1">Password</label>
            <div className="relative">
              <Lock className="w-3.5 h-3.5 text-clima-muted dark:text-darkClima-muted absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-clima-subtle dark:bg-darkClima-subtle border border-clima-border dark:border-darkClima-border rounded-lg py-2 pl-9 pr-3 text-clima-text dark:text-darkClima-text placeholder-clima-muted dark:placeholder-darkClima-muted focus:outline-none focus:border-clima-accent dark:focus:border-darkClima-accent"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 bg-clima-accent dark:bg-darkClima-accent text-white dark:text-darkClima-bg font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-colors mt-2 shadow-sm"
          >
            {submitting ? 'Authenticating...' : isRegister ? 'Register Account' : 'Sign In'}
          </button>
        </form>

        {/* Toggle Mode */}
        <div className="text-center pt-2 border-t border-clima-border dark:border-darkClima-border text-xs">
          {isRegister ? (
            <span className="text-clima-muted dark:text-darkClima-muted">
              Already registered?{' '}
              <button
                type="button"
                onClick={() => setIsRegister(false)}
                className="text-clima-accent dark:text-darkClima-accent hover:underline font-semibold"
              >
                Sign In
              </button>
            </span>
          ) : (
            <span className="text-clima-muted dark:text-darkClima-muted">
              Need access?{' '}
              <button
                type="button"
                onClick={() => setIsRegister(true)}
                className="text-clima-accent dark:text-darkClima-accent hover:underline font-semibold"
              >
                Register
              </button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
