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
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-navy-900 border border-slate-700 rounded-lg max-w-sm w-full p-6 relative shadow-2xl space-y-4">
        {/* Close Button */}
        <button
          onClick={closeAuthModal}
          className="absolute top-4 right-4 text-slate-400 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="space-y-1">
          <h3 className="text-lg font-bold text-white font-mono">
            {isRegister ? 'Analyst Registration' : 'Analyst Authentication'}
          </h3>
          <p className="text-xs text-slate-400 font-mono">
            Access secure saved locations, reports and alert rules.
          </p>
        </div>

        {error && (
          <div className="p-2.5 bg-red-950/60 border border-red-800 rounded flex items-center space-x-2 text-xs text-red-300 font-mono">
            <ShieldAlert className="w-4 h-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3 text-xs">
          {isRegister && (
            <div>
              <label className="text-slate-400 block mb-1 font-mono">Full Name</label>
              <div className="relative">
                <User className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Dr. Jane Doe"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-navy-950 border border-slate-700 rounded py-2 pl-9 pr-3 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyanAccent font-mono"
                />
              </div>
            </div>
          )}

          <div>
            <label className="text-slate-400 block mb-1 font-mono">Email Address</label>
            <div className="relative">
              <Mail className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="email"
                placeholder="analyst@aerosense.ai"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-navy-950 border border-slate-700 rounded py-2 pl-9 pr-3 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyanAccent font-mono"
              />
            </div>
          </div>

          <div>
            <label className="text-slate-400 block mb-1 font-mono">Password</label>
            <div className="relative">
              <Lock className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-navy-950 border border-slate-700 rounded py-2 pl-9 pr-3 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyanAccent font-mono"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2.5 bg-cyanAccent text-navy-950 font-bold rounded hover:bg-cyan-300 disabled:opacity-50 transition-colors mt-2 font-mono"
          >
            {submitting ? 'Authenticating...' : isRegister ? 'Register Account' : 'Sign In'}
          </button>
        </form>

        {/* Toggle Mode */}
        <div className="text-center pt-2 border-t border-slate-800 text-xs font-mono">
          {isRegister ? (
            <span className="text-slate-400">
              Already registered?{' '}
              <button
                type="button"
                onClick={() => setIsRegister(false)}
                className="text-cyanAccent hover:underline font-semibold"
              >
                Sign In
              </button>
            </span>
          ) : (
            <span className="text-slate-400">
              Need access?{' '}
              <button
                type="button"
                onClick={() => setIsRegister(true)}
                className="text-cyanAccent hover:underline font-semibold"
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
