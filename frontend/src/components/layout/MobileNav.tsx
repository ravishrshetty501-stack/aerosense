import React from 'react';
import { NavTab } from './Sidebar';
import {
  Globe,
  LayoutDashboard,
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
    { id: 'map' as NavTab, label: 'Map', icon: Globe },
    { id: 'dashboard' as NavTab, label: 'Overview', icon: LayoutDashboard },
    { id: 'analytics' as NavTab, label: 'Trends', icon: LineChart },
    { id: 'ai' as NavTab, label: 'Assistant', icon: Bot },
    { id: 'compare' as NavTab, label: 'Compare', icon: GitCompare },
    { id: 'advisor' as NavTab, label: 'Health', icon: Activity },
    { id: 'reports' as NavTab, label: 'Reports', icon: FileText },
    { id: 'alerts' as NavTab, label: 'Alerts', icon: BellRing },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 h-14 bg-clima-surface dark:bg-darkClima-surface border-t border-clima-border dark:border-darkClima-border flex items-center justify-around px-1 z-40 transition-colors">
      {items.map((item) => {
        const Icon = item.icon;
        const isActive = currentTab === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onSelectTab(item.id)}
            className={`flex flex-col items-center justify-center flex-1 py-1 transition-colors ${
              isActive
                ? 'text-clima-accent dark:text-darkClima-accent font-semibold'
                : 'text-clima-muted dark:text-darkClima-muted hover:text-clima-text dark:hover:text-darkClima-text'
            }`}
          >
            <Icon className="w-4 h-4" />
            <span className="text-[9px] font-sans mt-0.5">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
};
