import React, { useState, useEffect, useRef } from 'react';
import { useAQI } from '../../context/AQIContext';
import { useAuth } from '../../context/AuthContext';
import { AQIStandard } from '../../types/airQuality';
import { Search, ShieldAlert, User as UserIcon, RefreshCw, Compass, ChevronDown, Check } from 'lucide-react';
import { api } from '../../services/api';

export const Navbar: React.FC = () => {
  const { activeCity, setActiveCity, standard, setStandard, loading, refreshData, lastUpdated, airQuality } = useAQI();
  const { user, openAuthModal, logout } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // Close search on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Debounced search
  useEffect(() => {
    if (searchQuery.trim().length < 2) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await api.searchLocations(searchQuery);
        setSearchResults(results);
        setShowDropdown(true);
      } catch (err) {
        console.error(err);
      } finally {
        setIsSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const selectCity = (item: any) => {
    setActiveCity({
      name: item.name,
      country: item.country,
      latitude: item.latitude,
      longitude: item.longitude,
    });
    setSearchQuery('');
    setShowDropdown(false);
  };

  const getStandardLabel = (std: AQIStandard) => {
    switch (std) {
      case 'US_EPA': return 'US EPA AQI';
      case 'INDIA_CPCB': return 'India CPCB NAQI';
      case 'EUROPEAN_AQI': return 'European EAQI';
      default: return std;
    }
  };

  return (
    <header className="h-16 border-b border-surface-border bg-navy-900/90 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between sticky top-0 z-40">
      {/* Brand & Live Indicator */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-md bg-gradient-to-br from-cyanAccent to-blue-600 flex items-center justify-center shadow-lg shadow-cyanAccent/20">
            <Compass className="w-5 h-5 text-navy-950 font-bold" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-base sm:text-lg font-bold tracking-tight text-white">
                AEROSENSE<span className="text-cyanAccent font-mono ml-1">AI</span>
              </span>
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
            </div>
            <p className="hidden md:block text-[10px] text-slate-400 uppercase tracking-widest font-mono">
              Global Environmental Intelligence
            </p>
          </div>
        </div>
      </div>

      {/* Global Location Search */}
      <div className="relative flex-1 max-w-md mx-4" ref={searchRef}>
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search global city, coordinates or station..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => searchQuery.length >= 2 && setShowDropdown(true)}
            className="w-full bg-navy-950/80 border border-slate-700/60 rounded-md py-1.5 pl-9 pr-8 text-xs sm:text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyanAccent transition-colors"
          />
          {isSearching && (
            <RefreshCw className="w-3.5 h-3.5 text-cyanAccent animate-spin absolute right-3 top-1/2 -translate-y-1/2" />
          )}
        </div>

        {/* Autocomplete Dropdown */}
        {showDropdown && searchResults.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-navy-900 border border-slate-700 rounded-md shadow-2xl overflow-hidden z-50 py-1">
            {searchResults.map((item, idx) => (
              <button
                key={idx}
                onClick={() => selectCity(item)}
                className="w-full px-3 py-2 text-left hover:bg-navy-800 flex items-center justify-between text-xs sm:text-sm transition-colors"
              >
                <div>
                  <span className="font-medium text-slate-200">{item.name}</span>
                  {item.country && <span className="text-slate-400 text-xs ml-2">({item.country})</span>}
                </div>
                <span className="text-[10px] font-mono text-slate-500">
                  {item.latitude.toFixed(2)}°, {item.longitude.toFixed(2)}°
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right Controls: Standard Selector & Auth */}
      <div className="flex items-center space-x-2 sm:space-x-4">
        {/* AQI Standard Selector */}
        <div className="hidden lg:flex items-center bg-navy-950 border border-slate-800 rounded-md p-0.5">
          {(['US_EPA', 'INDIA_CPCB', 'EUROPEAN_AQI'] as AQIStandard[]).map((std) => (
            <button
              key={std}
              onClick={() => setStandard(std)}
              className={`px-2.5 py-1 text-[11px] font-mono rounded transition-colors ${
                standard === std
                  ? 'bg-cyanAccent/15 text-cyanAccent font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {std === 'US_EPA' ? 'US EPA' : std === 'INDIA_CPCB' ? 'India CPCB' : 'EU EAQI'}
            </button>
          ))}
        </div>

        {/* Sync / Refresh Button */}
        <button
          onClick={refreshData}
          disabled={loading}
          title="Refresh Environmental Data"
          className="p-1.5 text-slate-400 hover:text-cyanAccent hover:bg-navy-850 rounded-md border border-transparent hover:border-slate-800 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyanAccent' : ''}`} />
        </button>

        {/* User Auth Profile */}
        {user ? (
          <div className="flex items-center space-x-2">
            <div className="hidden sm:block text-right">
              <div className="text-xs font-medium text-slate-200">{user.full_name || user.email.split('@')[0]}</div>
              <div className="text-[10px] text-slate-400 font-mono">Verified Analyst</div>
            </div>
            <button
              onClick={logout}
              title="Logout"
              className="p-1.5 bg-navy-800 hover:bg-navy-700 text-slate-300 rounded-md border border-slate-700 text-xs"
            >
              <UserIcon className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <button
            onClick={openAuthModal}
            className="px-3 py-1.5 bg-cyanAccent/10 hover:bg-cyanAccent/20 border border-cyanAccent/30 text-cyanAccent text-xs font-medium rounded-md transition-colors flex items-center space-x-1"
          >
            <UserIcon className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Sign In</span>
          </button>
        )}
      </div>
    </header>
  );
};
