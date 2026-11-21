import React, { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  Globe,
  LineChart,
  Bot,
  GitCompare,
  Activity,
  FileText,
  BellRing,
  ActivitySquare,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { api } from '../../services/api';

export type NavTab = 'dashboard' | 'map' | 'analytics' | 'ai' | 'compare' | 'advisor' | 'reports' | 'alerts';

interface SidebarProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab }) => {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    const saved = localStorage.getItem('aerosense_rail_collapsed');
    return saved === 'true';
  });
  const [networkInfo, setNetworkInfo] = useState<any>(null);

  useEffect(() => {
    localStorage.setItem('aerosense_rail_collapsed', String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    let mounted = true;
    const fetchStatus = async () => {
      try {
        const data = await api.getNetworkStatus();
        if (mounted) setNetworkInfo(data);
      } catch (e) {
        if (mounted) setNetworkInfo(null);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const navItems = [
    { id: 'dashboard' as NavTab, label: 'Overview', icon: LayoutDashboard },
    { id: 'map' as NavTab, label: 'Global Map', icon: Globe },
    { id: 'analytics' as NavTab, label: 'Analytics', icon: LineChart },
    { id: 'ai' as NavTab, label: 'AI Assistant', icon: Bot },
    { id: 'compare' as NavTab, label: 'City Comparison', icon: GitCompare },
    { id: 'advisor' as NavTab, label: 'Health & Activity', icon: Activity },
    { id: 'reports' as NavTab, label: 'Reports', icon: FileText },
    { id: 'alerts' as NavTab, label: 'Alerts', icon: BellRing },
  ];

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case 'connected':
        return <span className="text-atlas-success dark:text-darkAtlas-success font-mono text-[9px] font-semibold">Online</span>;
      case 'degraded':
        return <span className="text-atlas-warning dark:text-darkAtlas-warning font-mono text-[9px] font-semibold">Degraded</span>;
      case 'not_configured':
        return <span className="text-atlas-muted dark:text-darkAtlas-muted font-mono text-[9px]">Standby</span>;
      default:
        return <span className="text-atlas-danger dark:text-darkAtlas-danger font-mono text-[9px]">Offline</span>;
    }
  };

  return (
    <aside
      className={`border-r border-atlas-border dark:border-darkAtlas-border bg-atlas-surface dark:bg-darkAtlas-surface flex flex-col justify-between shrink-0 hidden md:flex transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-56'
      }`}
    >
      {/* Navigation Links */}
      <div className="p-2 space-y-1">
        <div className="flex items-center justify-between px-2.5 py-2">
          {!collapsed && (
            <span className="text-[10px] font-mono uppercase tracking-wider text-atlas-muted dark:text-darkAtlas-muted font-semibold">
              Observatory
            </span>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? 'Expand Navigation' : 'Collapse Navigation'}
            className="p-1 text-atlas-muted dark:text-darkAtlas-muted hover:text-atlas-text dark:hover:text-darkAtlas-text rounded hover:bg-atlas-subtle dark:hover:bg-darkAtlas-subtle transition-colors ml-auto"
          >
            {collapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
          </button>
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              title={collapsed ? item.label : undefined}
              className={`w-full flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-atlas-subtle dark:bg-darkAtlas-subtle text-atlas-accent dark:text-darkAtlas-accent font-semibold border-l-2 border-atlas-accent dark:border-darkAtlas-accent shadow-sm'
                  : 'text-atlas-muted dark:text-darkAtlas-muted hover:text-atlas-text dark:hover:text-darkAtlas-text hover:bg-atlas-subtle/50 dark:hover:bg-darkAtlas-subtle/50'
              } ${collapsed ? 'justify-center px-0' : ''}`}
            >
              <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-atlas-accent dark:text-darkAtlas-accent' : 'text-atlas-muted dark:text-darkAtlas-muted'}`} />
              {!collapsed && <span className="font-sans truncate">{item.label}</span>}
            </button>
          );
        })}
      </div>

      {/* Telemetry Status Footer */}
      {!collapsed && (
        <div className="p-3 border-t border-atlas-border dark:border-darkAtlas-border bg-atlas-subtle/40 dark:bg-darkAtlas-subtle/40">
          <div className="bg-atlas-surface dark:bg-darkAtlas-surface rounded-lg p-2.5 border border-atlas-border dark:border-darkAtlas-border space-y-1.5 shadow-sm">
            <div className="flex items-center justify-between border-b border-atlas-border dark:border-darkAtlas-border pb-1">
              <span className="text-[10px] font-mono text-atlas-muted dark:text-darkAtlas-muted uppercase tracking-wider flex items-center">
                <ActivitySquare className="w-3 h-3 text-atlas-accent dark:text-darkAtlas-accent mr-1" /> Telemetry
              </span>
              <span className="flex h-1.5 w-1.5 rounded-full bg-atlas-success dark:bg-darkAtlas-success" />
            </div>

            <div className="space-y-1 pt-0.5 text-[10px]">
              <div className="flex items-center justify-between">
                <span className="text-atlas-muted dark:text-darkAtlas-muted font-sans">WAQI Ground:</span>
                {getStatusBadge(networkInfo?.providers?.waqi?.status)}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-atlas-muted dark:text-darkAtlas-muted font-sans">CAMS Model:</span>
                {getStatusBadge(networkInfo?.providers?.open_meteo?.status)}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-atlas-muted dark:text-darkAtlas-muted font-sans">Gemini AI:</span>
                {getStatusBadge(networkInfo?.providers?.gemini_ai?.status)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Collapsed Status Dot */}
      {collapsed && (
        <div className="p-3 flex justify-center border-t border-atlas-border dark:border-darkAtlas-border">
          <span className="flex h-2 w-2 rounded-full bg-atlas-success dark:bg-darkAtlas-success" title="Telemetry Feed Active" />
        </div>
      )}
    </aside>
  );
};
