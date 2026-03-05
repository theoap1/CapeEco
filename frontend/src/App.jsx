import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Moon, Sun, Building2, LogOut, Map, MessageSquare, FileText } from 'lucide-react';
import AddressSearchBar from './components/AddressSearchBar';
import LoginPage from './pages/LoginPage';
import MapView from './pages/MapView';
import AIWorkspace from './pages/AIWorkspace';
import ReportsView from './pages/ReportsView';
import FinancialsPage from './pages/FinancialsPage';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { useDarkMode } from './hooks/useDarkMode';

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-gray-950">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-ocean-600/20 border border-ocean-500/30 flex items-center justify-center">
            <Building2 className="w-5 h-5 text-ocean-400" />
          </div>
          <p className="text-sm text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

const TABS = [
  { id: 'map', label: 'Home', icon: Map, path: '/' },
  { id: 'ai', label: 'AI Workspace', icon: MessageSquare, path: '/ai' },
  { id: 'reports', label: 'Reports', icon: FileText, path: '/reports' },
];

function AppShell() {
  const { logout, user } = useAuth();
  const [dark, setDark] = useDarkMode();
  const location = useLocation();
  const navigate = useNavigate();
  const [selectedPropertyId, setSelectedPropertyId] = useState(null);

  const activeTab = TABS.find(t => t.path === location.pathname)?.id
    || (location.pathname === '/' ? 'map' : 'map');

  const handleSearchSelect = (result) => {
    setSelectedPropertyId(result.id);
    // Stay on current page if on /ai, otherwise go to map
    if (location.pathname !== '/' && location.pathname !== '/ai') {
      navigate('/');
    }
  };

  return (
    <div className={`h-screen w-screen flex flex-col bg-gray-950 font-sans ${dark ? 'dark' : ''}`}>
      {/* Top bar */}
      <header className="h-12 bg-gray-950/95 backdrop-blur-md flex items-center px-4 gap-3 z-[1001] shrink-0 border-b border-gray-800/40">
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-7 h-7 rounded-lg bg-ocean-600/20 border border-ocean-500/30 flex items-center justify-center">
            <Building2 className="w-3.5 h-3.5 text-ocean-400" />
          </div>
          <span className="text-sm font-bold text-white hidden sm:inline tracking-wider">
            Siteline
          </span>
        </div>

        {/* Tab bar */}
        <nav className="flex items-center gap-0.5 ml-4">
          {TABS.map(tab => {
            const Icon = tab.icon;
            const isActive = tab.id === activeTab;
            return (
              <button
                key={tab.id}
                onClick={() => navigate(tab.path)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'text-ocean-400 border-b-2 border-ocean-400'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50 border-b-2 border-transparent'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span className="hidden md:inline">{tab.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="flex-1" />

        <AddressSearchBar onSelect={handleSearchSelect} />

        <div className="flex items-center gap-1.5 shrink-0">
          {user && (
            <span className="text-xs text-gray-500 hidden lg:inline">
              {user.email}
            </span>
          )}
          <button
            onClick={() => setDark(!dark)}
            className="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center
                       hover:bg-gray-700 transition-colors"
          >
            {dark ? <Sun className="w-3.5 h-3.5 text-fynbos-400" /> : <Moon className="w-3.5 h-3.5 text-gray-400" />}
          </button>
          <button
            onClick={logout}
            title="Sign out"
            className="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center
                       hover:bg-red-900/50 hover:text-red-400 transition-colors text-gray-500"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>
      <div className="h-px bg-gradient-to-r from-transparent via-ocean-500/20 to-transparent" />

      {/* Content area */}
      <div className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={
            <MapView
              dark={dark}
              selectedPropertyId={selectedPropertyId}
              setSelectedPropertyId={setSelectedPropertyId}
            />
          } />
          <Route path="/ai" element={
            <AIWorkspace
              selectedPropertyId={selectedPropertyId}
              onClearProperty={() => setSelectedPropertyId(null)}
            />
          } />
          <Route path="/reports" element={<ReportsView />} />
          <Route path="/property/:id/financials" element={<FinancialsPage />} />
        </Routes>
      </div>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/*" element={<ProtectedRoute><AppShell /></ProtectedRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
