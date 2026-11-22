import React, { useState, useEffect, Suspense, lazy } from 'react';
import { AuthProvider } from './context/AuthContext';
import { AQIProvider } from './context/AQIContext';
import { ThemeProvider } from './context/ThemeContext';
import { Navbar } from './components/layout/Navbar';
import { Sidebar, NavTab } from './components/layout/Sidebar';
import { MobileNav } from './components/layout/MobileNav';
import { AuthModal } from './components/auth/AuthModal';
import { WifiOff, Loader2 } from 'lucide-react';

// Dynamic code-splitting for high-performance lazy view loading
const OverviewDashboard = lazy(() =>
  import('./components/dashboard/OverviewDashboard').then((m) => ({ default: m.OverviewDashboard }))
);
const GlobalPollutionMap = lazy(() =>
  import('./components/map/GlobalPollutionMap').then((m) => ({ default: m.GlobalPollutionMap }))
);
const AnalyticsView = lazy(() =>
  import('./components/analytics/AnalyticsView').then((m) => ({ default: m.AnalyticsView }))
);
const AIAssistantView = lazy(() =>
  import('./components/ai/AIAssistantView').then((m) => ({ default: m.AIAssistantView }))
);
const CityComparisonView = lazy(() =>
  import('./components/compare/CityComparisonView').then((m) => ({ default: m.CityComparisonView }))
);
const HealthAdvisorView = lazy(() =>
  import('./components/advisor/HealthAdvisorView').then((m) => ({ default: m.HealthAdvisorView }))
);
const ReportsView = lazy(() =>
  import('./components/reports/ReportsView').then((m) => ({ default: m.ReportsView }))
);
const AlertsView = lazy(() =>
  import('./components/alerts/AlertsView').then((m) => ({ default: m.AlertsView }))
);

const ViewLoadingFallback: React.FC = () => (
  <div className="flex flex-col items-center justify-center min-h-[45vh] space-y-3 font-sans" role="status" aria-live="polite">
    <Loader2 className="w-6 h-6 text-atlas-accent dark:text-darkAtlas-accent animate-spin" />
    <span className="text-xs text-atlas-muted dark:text-darkAtlas-muted font-mono tracking-wider">
      Loading workspace view...
    </span>
  </div>
);

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
          <Suspense fallback={<ViewLoadingFallback />}>
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
          </Suspense>
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
