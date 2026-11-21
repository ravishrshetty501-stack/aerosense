import React from 'react';
import {
  LayoutDashboard,
  Map as MapIcon,
  LineChart,
  Bot,
  GitCompare,
  Activity,
  FileText,
  BellRing
} from 'lucide-react';

export type NavTab = 'dashboard' | 'map' | 'analytics' | 'ai' | 'compare' | 'advisor' | 'reports' | 'alerts';

interface SidebarProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab }) => {
  const navItems = [
    { id: 'dashboard' as NavTab, label: 'Overview Dashboard', code: '01', icon: LayoutDashboard },
    { id: 'map' as NavTab, label: 'Global Pollution Map', code: '02', icon: MapIcon },
    { id: 'analytics' as NavTab, label: 'Pollution Analytics', code: '03', icon: LineChart },
    { id: 'ai' as NavTab, label: 'GenAI Assistant', code: '04', icon: Bot, highlight: true },
    { id: 'compare' as NavTab, label: 'City Comparison', code: '05', icon: GitCompare },
    { id: 'advisor' as NavTab, label: 'Health & Activity', code: '06', icon: Activity },
    { id: 'reports' as NavTab, label: 'Environmental Reports', code: '07', icon: FileText },
    { id: 'alerts' as NavTab, label: 'Intelligent Alerts', code: '08', icon: BellRing },
  ];

  return (
    <aside className="w-64 border-r border-surface-border bg-navy-950/80 flex flex-col justify-between shrink-0 hidden md:flex">
      {/* Navigation Links */}
      <div className="p-3 space-y-1">
        <div className="px-3 py-2 text-[10px] font-mono uppercase tracking-widest text-slate-500">
          Core Modules
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-md text-xs font-medium transition-all ${
                isActive
                  ? 'bg-navy-800 text-cyanAccent border-l-2 border-cyanAccent shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-navy-900'
              }`}
            >
              <div className="flex items-center space-x-3">
                <Icon className={`w-4 h-4 ${isActive ? 'text-cyanAccent' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </div>
              <span className={`text-[10px] font-mono ${isActive ? 'text-cyanAccent' : 'text-slate-600'}`}>
                {item.code}
              </span>
            </button>
          );
        })}
      </div>

      {/* Terminal Info Footer */}
      <div className="p-4 border-t border-surface-border bg-navy-950/50">
        <div className="bg-navy-900/60 rounded p-2.5 border border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
            <span>NETWORK</span>
            <span className="text-emerald-400">CONNECTED</span>
          </div>
          <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
            <span>OPENAQ V3</span>
            <span className="text-cyanAccent">STANDBY</span>
          </div>
          <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
            <span>OPEN-METEO</span>
            <span className="text-emerald-400">VERIFIED</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
