import React from 'react';
import { NavTab } from './Sidebar';
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

interface MobileNavProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
}

export const MobileNav: React.FC<MobileNavProps> = ({ currentTab, onSelectTab }) => {
  const items = [
    { id: 'dashboard' as NavTab, label: 'Overview', icon: LayoutDashboard },
    { id: 'map' as NavTab, label: 'Map', icon: MapIcon },
    { id: 'analytics' as NavTab, label: 'Trends', icon: LineChart },
    { id: 'ai' as NavTab, label: 'Assistant', icon: Bot },
    { id: 'compare' as NavTab, label: 'Compare', icon: GitCompare },
    { id: 'advisor' as NavTab, label: 'Health', icon: Activity },
    { id: 'reports' as NavTab, label: 'Reports', icon: FileText },
    { id: 'alerts' as NavTab, label: 'Alerts', icon: BellRing },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 h-14 bg-navy-900 border-t border-slate-800 flex items-center justify-around px-2 z-40">
      {items.map((item) => {
        const Icon = item.icon;
        const isActive = currentTab === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onSelectTab(item.id)}
            className={`flex flex-col items-center justify-center flex-1 py-1 ${
              isActive ? 'text-cyanAccent' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Icon className="w-4 h-4" />
            <span className="text-[9px] font-mono mt-0.5">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
};
