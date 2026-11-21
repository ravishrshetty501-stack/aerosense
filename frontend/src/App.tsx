import React, { useState, useEffect } from 'react';
import { AuthProvider } from './context/AuthContext';
import { AQIProvider } from './context/AQIContext';
import { Navbar } from './components/layout/Navbar';
import { Sidebar, NavTab } from './components/layout/Sidebar';
import { MobileNav } from './components/layout/MobileNav';
import { OverviewDashboard } from './components/dashboard/OverviewDashboard';
import { GlobalPollutionMap } from './components/map/GlobalPollutionMap';
import { AnalyticsView } from './components/analytics/AnalyticsView';
import { AIAssistantView } from './components/ai/AIAssistantView';
import { CityComparisonView } from './components/compare/CityComparisonView';
import { HealthAdvisorView } from './components/advisor/HealthAdvisorView';
import { ReportsView } from './components/reports/ReportsView';
import { AlertsView } from './components/alerts/AlertsView';
import { AuthModal } from './components/auth/AuthModal';
import { WifiOff } from 'lucide-react';

const AppContent: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return (
    <div className="min-h-screen bg-navy-950 text-slate-100 flex flex-col font-sans selection:bg-cyanAccent/20 selection:text-cyanAccent">
      {/* Offline Warning Banner */}
      {isOffline && (
        <div className="bg-amber-950/90 border-b border-amber-800 text-amber-200 px-4 py-2 text-xs font-mono flex items-center justify-center space-x-2 z-50">
          <WifiOff className="w-4 h-4 text-amber-400" />
          <span>OFFLINE CACHE MODE: Displaying previously cached environmental records. Live sensor streaming paused.</span>
        </div>
      )}

      {/* Top Navbar */}
      <Navbar />

      {/* Main Workspace Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <Sidebar currentTab={currentTab} onSelectTab={setCurrentTab} />

        {/* Content View Area */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 mb-14 md:mb-0">
          {currentTab === 'dashboard' && <OverviewDashboard />}
          {currentTab === 'map' && <GlobalPollutionMap />}
          {currentTab === 'analytics' && <AnalyticsView />}
          {currentTab === 'ai' && <AIAssistantView />}
          {currentTab === 'compare' && <CityComparisonView />}
          {currentTab === 'advisor' && <HealthAdvisorView />}
          {currentTab === 'reports' && <ReportsView />}
          {currentTab === 'alerts' && <AlertsView />}
        </main>
      </div>

      {/* Mobile Bottom Navigation */}
      <MobileNav currentTab={currentTab} onSelectTab={setCurrentTab} />

      {/* Authentication Modal */}
      <AuthModal />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AQIProvider>
        <AppContent />
      </AQIProvider>
    </AuthProvider>
  );
};

export default App;
