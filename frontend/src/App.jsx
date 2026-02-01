import { useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Moon, Sun, Leaf, LogOut } from 'lucide-react';
import AddressSearchBar from './components/AddressSearchBar';
import InteractiveMap from './components/InteractiveMap';
import PropertySidebar from './components/PropertySidebar';
import LayerControl from './components/LayerControl';
import LoginPage from './pages/LoginPage';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { useDarkMode } from './hooks/useDarkMode';
import { getProperty } from './utils/api';

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-ocean-500 to-protea-600 flex items-center justify-center">
            <Leaf className="w-5 h-5 text-white" />
          </div>
          <p className="text-sm text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function MainApp() {
  const { logout, user } = useAuth();
  const [dark, setDark] = useDarkMode();
  const [selectedPropertyId, setSelectedPropertyId] = useState(null);
  const [flyTo, setFlyTo] = useState(null);
  const [selectedGeometry, setSelectedGeometry] = useState(null);
  const [constraintMapData, setConstraintMapData] = useState(null);
  const [comparisonData, setComparisonData] = useState(null);
  const [layers, setLayers] = useState({
    biodiversity: { active: true, label: 'Biodiversity (CBA/ESA)' },
  });

  const handleSearchSelect = useCallback(async (result) => {
    setSelectedPropertyId(result.id);
    setConstraintMapData(null);
    setComparisonData(null);
    if (result.centroid_lat && result.centroid_lon) {
      setFlyTo({ center: [result.centroid_lat, result.centroid_lon], zoom: 17 });
    }
    try {
      const prop = await getProperty(result.id);
      if (prop.geometry) {
        setSelectedGeometry({
          type: 'Feature',
          geometry: prop.geometry,
          properties: {},
        });
      }
    } catch {
      // geometry fetch failed silently
    }
  }, []);

  const handlePropertyClick = useCallback(async (props) => {
    if (!props.id) return;
    setSelectedPropertyId(props.id);
    setConstraintMapData(null);
    setComparisonData(null);
    try {
      const prop = await getProperty(props.id);
      if (prop.geometry) {
        setSelectedGeometry({
          type: 'Feature',
          geometry: prop.geometry,
          properties: {},
        });
      }
    } catch {
      // ignore
    }
  }, []);

  const handleClose = useCallback(() => {
    setSelectedPropertyId(null);
    setSelectedGeometry(null);
    setConstraintMapData(null);
    setComparisonData(null);
  }, []);

  const toggleLayer = useCallback((key) => {
    setLayers(prev => ({
      ...prev,
      [key]: { ...prev[key], active: !prev[key].active },
    }));
  }, []);

  return (
    <div className={`h-screen w-screen flex flex-col ${dark ? 'dark' : ''}`}>
      {/* Top bar */}
      <header className="h-14 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800
                         flex items-center px-4 gap-4 z-[1001] shrink-0">
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-ocean-500 to-protea-600 flex items-center justify-center">
            <Leaf className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-bold text-gray-900 dark:text-white hidden sm:inline">
            CapeEco
          </span>
        </div>

        <AddressSearchBar onSelect={handleSearchSelect} />

        <div className="ml-auto flex items-center gap-2 shrink-0">
          {user && (
            <span className="text-xs text-gray-500 dark:text-gray-400 hidden md:inline">
              {user.email}
            </span>
          )}
          <button
            onClick={() => setDark(!dark)}
            className="w-9 h-9 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center
                       hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            {dark ? <Sun className="w-4 h-4 text-fynbos-400" /> : <Moon className="w-4 h-4 text-gray-600" />}
          </button>
          <button
            onClick={logout}
            title="Sign out"
            className="w-9 h-9 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center
                       hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-600 transition-colors text-gray-500"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main content: map + sidebar */}
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 relative">
          <InteractiveMap
            dark={dark}
            flyToCenter={flyTo?.center}
            flyToZoom={flyTo?.zoom}
            selectedPropertyGeometry={selectedGeometry}
            onPropertyClick={handlePropertyClick}
            showBioLayer={layers.biodiversity.active}
            constraintMapData={constraintMapData}
            comparisonData={comparisonData}
          />
          <LayerControl layers={layers} onToggle={toggleLayer} />
        </div>

        {selectedPropertyId && (
          <PropertySidebar
            propertyId={selectedPropertyId}
            onClose={handleClose}
            onShowConstraintMap={setConstraintMapData}
            onShowComparison={setComparisonData}
          />
        )}
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
          <Route path="/*" element={<ProtectedRoute><MainApp /></ProtectedRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
