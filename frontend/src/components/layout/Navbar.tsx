import React, { useState, useEffect, useRef } from 'react';
import { useAQI } from '../../context/AQIContext';
import { useAuth } from '../../context/AuthContext';
import { useTheme, ThemeMode } from '../../context/ThemeContext';
import { AQIStandard } from '../../types/airQuality';
import {
  Search,
  User as UserIcon,
  RefreshCw,
  Sun,
  Moon,
  Laptop,
  MapPin,
  X,
  ChevronDown,
  Layers
} from 'lucide-react';
import { api } from '../../services/api';

export const Navbar: React.FC = () => {
  const { activeCity, setActiveCity, standard, setStandard, loading, refreshData } = useAQI();
  const { user, openAuthModal, logout } = useAuth();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [showThemeMenu, setShowThemeMenu] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const themeRef = useRef<HTMLDivElement>(null);

  // Close menus on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
      if (themeRef.current && !themeRef.current.contains(e.target as Node)) {
        setShowThemeMenu(false);
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
    }, 280);
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

  return (
    <header className="h-14 border-b border-atlas-border dark:border-darkAtlas-border bg-atlas-surface dark:bg-darkAtlas-surface px-4 sm:px-6 flex items-center justify-between sticky top-0 z-40 transition-colors">
      {/* Brand & Wordmark */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2">
          {/* Atlas Explorer Compass Hex Mark */}
          <div className="w-6 h-6 rounded-md bg-atlas-accent dark:bg-darkAtlas-accent text-white dark:text-darkAtlas-bg flex items-center justify-center font-bold text-xs shadow-sm">
            <span className="font-mono text-[11px]">A</span>
          </div>

          <div className="flex items-baseline space-x-1.5">
            <span className="text-base font-bold tracking-tight text-atlas-text dark:text-darkAtlas-text font-sans">
              AeroSense<span className="text-atlas-accent dark:text-darkAtlas-accent ml-0.5 font-semibold">AI</span>
            </span>
            <span className="hidden xl:inline-block text-[10px] uppercase tracking-wider text-atlas-muted dark:text-darkAtlas-muted ml-2 font-mono border-l border-atlas-border dark:border-darkAtlas-border pl-2">
              Environmental Observatory
            </span>
          </div>
        </div>

        {/* Selected Location Pill */}
        <div className="hidden sm:flex items-center space-x-1 px-2.5 py-1 bg-atlas-subtle dark:bg-darkAtlas-subtle rounded-md border border-atlas-border dark:border-darkAtlas-border text-xs text-atlas-text dark:text-darkAtlas-text font-sans">
          <MapPin className="w-3 h-3 text-atlas-accent dark:text-darkAtlas-accent shrink-0" />
          <span className="font-medium truncate max-w-[130px]">{activeCity.name}</span>
          {activeCity.country && (
            <span className="text-atlas-muted dark:text-darkAtlas-muted text-[11px] truncate">
              ({activeCity.country})
            </span>
          )}
        </div>
      </div>

      {/* Global Location Search Input */}
      <div className="relative flex-1 max-w-sm sm:max-w-md mx-4" ref={searchRef}>
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-atlas-muted dark:text-darkAtlas-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search global city, coordinates or monitoring station..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => searchQuery.length >= 2 && setShowDropdown(true)}
            className="w-full bg-atlas-subtle dark:bg-darkAtlas-subtle border border-atlas-border dark:border-darkAtlas-border rounded-lg py-1.5 pl-8 pr-8 text-xs text-atlas-text dark:text-darkAtlas-text placeholder-atlas-muted dark:placeholder-darkAtlas-muted focus:outline-none focus:border-atlas-accent dark:focus:border-darkAtlas-accent transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => {
                setSearchQuery('');
                setSearchResults([]);
              }}
              className="absolute right-7 top-1/2 -translate-y-1/2 text-atlas-muted dark:text-darkAtlas-muted hover:text-atlas-text dark:hover:text-darkAtlas-text p-0.5"
            >
              <X className="w-3 h-3" />
            </button>
          )}
          {isSearching && (
            <RefreshCw className="w-3 h-3 text-atlas-accent dark:text-darkAtlas-accent animate-spin absolute right-3 top-1/2 -translate-y-1/2" />
          )}
        </div>

        {/* Autocomplete Dropdown */}
        {showDropdown && searchResults.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-atlas-surface dark:bg-darkAtlas-surface border border-atlas-border dark:border-darkAtlas-border rounded-lg shadow-floating dark:shadow-floating-dark overflow-hidden z-50 py-1">
            {searchResults.map((item, idx) => (
              <button
                key={idx}
                onClick={() => selectCity(item)}
                className="w-full px-3 py-2 text-left hover:bg-atlas-subtle dark:hover:bg-darkAtlas-subtle flex items-center justify-between text-xs transition-colors"
              >
                <div className="flex items-center space-x-1.5 truncate">
                  <MapPin className="w-3 h-3 text-atlas-muted dark:text-darkAtlas-muted shrink-0" />
                  <span className="font-medium text-atlas-text dark:text-darkAtlas-text">{item.name}</span>
                  {item.country && (
                    <span className="text-atlas-muted dark:text-darkAtlas-muted text-[11px] truncate">
                      ({item.country})
                    </span>
                  )}
                </div>
                <span className="text-[10px] font-mono text-atlas-muted dark:text-darkAtlas-muted shrink-0 ml-2">
                  {item.latitude.toFixed(2)}°, {item.longitude.toFixed(2)}°
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right Controls: Standard Selector, 3-Option Theme, Refresh & Auth */}
      <div className="flex items-center space-x-2 sm:space-x-2.5">
        {/* AQI Standard Selector */}
        <div className="hidden md:flex items-center bg-atlas-subtle dark:bg-darkAtlas-subtle border border-atlas-border dark:border-darkAtlas-border rounded-lg p-0.5 text-[11px]">
          {(['US_EPA', 'INDIA_CPCB', 'EUROPEAN_AQI'] as AQIStandard[]).map((std) => {
            const isSelected = standard === std;
            return (
              <button
                key={std}
                onClick={() => setStandard(std)}
                className={`px-2.5 py-1 rounded-md font-sans transition-all ${
                  isSelected
                    ? 'bg-atlas-surface dark:bg-darkAtlas-surface text-atlas-accent dark:text-darkAtlas-accent font-semibold shadow-sm'
                    : 'text-atlas-muted dark:text-darkAtlas-muted hover:text-atlas-text dark:hover:text-darkAtlas-text'
                }`}
              >
                {std === 'US_EPA' ? 'US EPA' : std === 'INDIA_CPCB' ? 'India CPCB' : 'EU EAQI'}
              </button>
            );
          })}
        </div>

        {/* 3-Option Theme Switcher (Light / Dark / System) */}
        <div className="relative" ref={themeRef}>
          <button
            onClick={() => setShowThemeMenu(!showThemeMenu)}
            title={`Theme: ${theme.toUpperCase()} (Click to change)`}
            className="p-1.5 text-atlas-muted dark:text-darkAtlas-muted hover:text-atlas-text dark:hover:text-darkAtlas-text hover:bg-atlas-subtle dark:hover:bg-darkAtlas-subtle rounded-lg border border-atlas-border dark:border-darkAtlas-border transition-colors flex items-center space-x-1"
          >
            {theme === 'system' ? (
              <Laptop className="w-3.5 h-3.5" />
            ) : resolvedTheme === 'dark' ? (
              <Moon className="w-3.5 h-3.5" />
            ) : (
              <Sun className="w-3.5 h-3.5" />
            )}
            <ChevronDown className="w-2.5 h-2.5 opacity-60" />
          </button>

          {showThemeMenu && (
            <div className="absolute right-0 mt-1 w-32 bg-atlas-surface dark:bg-darkAtlas-surface border border-atlas-border dark:border-darkAtlas-border rounded-lg shadow-floating dark:shadow-floating-dark py-1 z-50 text-xs font-sans">
              {(['light', 'dark', 'system'] as ThemeMode[]).map((t) => (
                <button
                  key={t}
                  onClick={() => {
                    setTheme(t);
                    setShowThemeMenu(false);
                  }}
                  className={`w-full px-3 py-1.5 text-left flex items-center space-x-2 transition-colors ${
                    theme === t
                      ? 'bg-atlas-subtle dark:bg-darkAtlas-subtle text-atlas-accent dark:text-darkAtlas-accent font-semibold'
                      : 'text-atlas-text dark:text-darkAtlas-text hover:bg-atlas-subtle/50 dark:hover:bg-darkAtlas-subtle/50'
                  }`}
                >
                  {t === 'light' && <Sun className="w-3.5 h-3.5 text-amber-500" />}
                  {t === 'dark' && <Moon className="w-3.5 h-3.5 text-indigo-400" />}
                  {t === 'system' && <Laptop className="w-3.5 h-3.5 text-atlas-muted dark:text-darkAtlas-muted" />}
                  <span className="capitalize">{t}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Sync / Refresh Button */}
        <button
          onClick={refreshData}
          disabled={loading}
          title="Refresh Atmospheric Telemetry"
          className="p-1.5 text-atlas-muted dark:text-darkAtlas-muted hover:text-atlas-accent dark:hover:text-darkAtlas-accent hover:bg-atlas-subtle dark:hover:bg-darkAtlas-subtle rounded-lg border border-atlas-border dark:border-darkAtlas-border transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-atlas-accent dark:text-darkAtlas-accent' : ''}`} />
        </button>

        {/* User Auth Profile */}
        {user ? (
          <div className="flex items-center space-x-2">
            <button
              onClick={logout}
              title={`Signed in as ${user.email} (Click to Logout)`}
              className="flex items-center space-x-1.5 px-2.5 py-1 bg-atlas-subtle dark:bg-darkAtlas-subtle border border-atlas-border dark:border-darkAtlas-border rounded-lg text-xs font-medium text-atlas-text dark:text-darkAtlas-text"
            >
              <UserIcon className="w-3 h-3 text-atlas-accent dark:text-darkAtlas-accent" />
              <span className="hidden lg:inline">{user.full_name || user.email.split('@')[0]}</span>
            </button>
          </div>
        ) : (
          <button
            onClick={openAuthModal}
            className="px-2.5 py-1 bg-atlas-accent dark:bg-darkAtlas-accent text-white dark:text-darkAtlas-bg text-xs font-medium rounded-lg transition-colors flex items-center space-x-1 shadow-sm"
          >
            <UserIcon className="w-3 h-3" />
            <span className="hidden sm:inline">Sign In</span>
          </button>
        )}
      </div>
    </header>
  );
};
