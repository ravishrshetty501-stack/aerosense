import React, { useState, useEffect } from 'react';
import { AuthProvider } from './context/AuthContext';
import { AQIProvider } from './context/AQIContext';
import { ThemeProvider } from './context/ThemeContext';
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
  const [currentTab, setCurrentTab] = useState<NavTab>('map'); // Default to Global Map per scientific exploration vision
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
    <div className="min-h-screen bg-clima-bg dark:bg-darkClima-bg text-clima-text dark:text-darkClima-text flex flex-col font-sans transition-colors duration-150">
      {/* Offline Alert Strip */}
      {isOffline && (
        <div className="bg-amber-100 dark:bg-amber-950/80 border-b border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-200 px-4 py-1.5 text-xs font-mono flex items-center justify-center space-x-2 z-50">
          <WifiOff className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
          <span>OFFLINE CACHE: Displaying previously recorded telemetry. Live synchronization paused.</span>
        </div>
      )}

      {/* Top Navigation */}
      <Navbar />

      {/* Main Workspace Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Navigation Rail */}
        <Sidebar currentTab={currentTab} onSelectTab={setCurrentTab} />

        {/* Content View Area */}
        <main className={`flex-1 overflow-y-auto mb-14 md:mb-0 ${currentTab === 'map' ? 'p-0 overflow-hidden' : 'p-4 sm:p-6 lg:p-8'}`}>
          {currentTab === 'dashboard' && (
            <OverviewDashboard
              onNavigateToMap={() => setCurrentTab('map')}
              onNavigateToAlerts={() => setCurrentTab('alerts')}
            />
          )}
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
    <ThemeProvider>
      <AuthProvider>
        <AQIProvider>
          <AppContent />
        </AQIProvider>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
