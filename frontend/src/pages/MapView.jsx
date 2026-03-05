import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import InteractiveMap from '../components/InteractiveMap';
import PropertySidebar from '../components/PropertySidebar';
import CommandHUD from '../components/CommandHUD';
import LayerControl from '../components/LayerControl';
import { VerticalResizeHandle, HorizontalResizeHandle } from '../components/ResizableLayout';
import { getProperty } from '../utils/api';
import { useMediaQuery } from '../hooks/useMediaQuery';

export default function MapView({ dark, selectedPropertyId, setSelectedPropertyId }) {
  const navigate = useNavigate();
  const mapViewRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const [flyTo, setFlyTo] = useState(null);
  const [selectedGeometry, setSelectedGeometry] = useState(null);
  const [constraintMapData, setConstraintMapData] = useState(null);
  const [sitePlanData, setSitePlanData] = useState(null);
  const [comparisonData, setComparisonData] = useState(null);
  const [layers, setLayers] = useState({
    biodiversity: { active: true, label: 'Biodiversity (CBA/ESA)' },
  });
  const prevPropertyId = useRef(null);
  const isMobile = useMediaQuery('(max-width: 768px)');

  // Panel dimensions with localStorage persistence
  const [detailsWidth, setDetailsWidth] = useState(() => {
    const saved = localStorage.getItem('siteline-details-width');
    return saved ? Number(saved) : 420;
  });
  const [hudHeight, setHudHeight] = useState(() => {
    const saved = localStorage.getItem('siteline-hud-height');
    return saved ? Number(saved) : 200;
  });

  // When selectedPropertyId changes, fetch geometry and fly to it
  useEffect(() => {
    if (!selectedPropertyId || selectedPropertyId === prevPropertyId.current) return;
    prevPropertyId.current = selectedPropertyId;
    setConstraintMapData(null);
    setSitePlanData(null);
    setComparisonData(null);

    getProperty(selectedPropertyId)
      .then((prop) => {
        if (prop.centroid_lat && prop.centroid_lon) {
          setFlyTo({ center: [prop.centroid_lat, prop.centroid_lon], zoom: 17 });
        }
        if (prop.geometry) {
          setSelectedGeometry({
            type: 'Feature',
            geometry: prop.geometry,
            properties: {},
          });
        }
      })
      .catch(() => {});
  }, [selectedPropertyId]);

  const handlePropertyClick = useCallback(async (props) => {
    if (!props.id) return;
    setSelectedPropertyId(props.id);
  }, [setSelectedPropertyId]);

  const handleClose = useCallback(() => {
    setSelectedPropertyId(null);
    setSelectedGeometry(null);
    setConstraintMapData(null);
    setSitePlanData(null);
    setComparisonData(null);
  }, [setSelectedPropertyId]);

  const toggleLayer = useCallback((key) => {
    setLayers(prev => ({
      ...prev,
      [key]: { ...prev[key], active: !prev[key].active },
    }));
  }, []);

  // Map instance ref for invalidateSize
  const handleMapReady = useCallback((map) => {
    mapInstanceRef.current = map;
  }, []);

  // Invalidate map size when panels resize
  useEffect(() => {
    const timer = setTimeout(() => {
      mapInstanceRef.current?.invalidateSize();
    }, 50);
    return () => clearTimeout(timer);
  }, [detailsWidth, hudHeight]);

  // Drag handlers for resizable panels
  const handleDetailsWidthDrag = useCallback((clientX) => {
    if (!mapViewRef.current) return;
    const rect = mapViewRef.current.getBoundingClientRect();
    const newWidth = rect.right - clientX;
    const clamped = Math.max(300, Math.min(700, newWidth));
    setDetailsWidth(clamped);
    localStorage.setItem('siteline-details-width', String(clamped));
  }, []);

  const handleHudHeightDrag = useCallback((clientY) => {
    if (!mapViewRef.current) return;
    const leftCol = mapViewRef.current.querySelector('[data-left-col]');
    if (!leftCol) return;
    const rect = leftCol.getBoundingClientRect();
    const newHeight = rect.bottom - clientY;
    const clamped = Math.max(44, Math.min(350, newHeight));
    setHudHeight(clamped);
    localStorage.setItem('siteline-hud-height', String(clamped));
  }, []);

  const hasProperty = !!selectedPropertyId;

  // Mobile layout: stack vertically
  if (isMobile) {
    return (
      <div className="h-full flex flex-col">
        <div className="flex-1 relative min-h-0">
          <InteractiveMap
            dark={dark}
            flyToCenter={flyTo?.center}
            flyToZoom={flyTo?.zoom}
            selectedPropertyGeometry={selectedGeometry}
            onPropertyClick={handlePropertyClick}
            showBioLayer={layers.biodiversity.active}
            constraintMapData={constraintMapData}
            sitePlanData={sitePlanData}
            comparisonData={comparisonData}
            onMapReady={handleMapReady}
          />
          <LayerControl layers={layers} onToggle={toggleLayer} position="top-left" />
        </div>
        {hasProperty && (
          <div className="h-1/3 overflow-y-auto border-t border-gray-800 bg-gray-950">
            <CommandHUD
              propertyId={selectedPropertyId}
              onClose={handleClose}
              onShowSitePlan={setSitePlanData}
              onShowConstraintMap={setConstraintMapData}
            />
          </div>
        )}
        {!hasProperty && (
          <CommandHUD
            propertyId={null}
            onClose={handleClose}
            onShowSitePlan={setSitePlanData}
            onShowConstraintMap={setConstraintMapData}
          />
        )}
      </div>
    );
  }

  // Desktop layout: map top-left, command bottom, details right, resizable
  return (
    <div ref={mapViewRef} className="h-full flex">
      {/* Left column: Map + Command HUD */}
      <div className="flex-1 flex flex-col min-w-0" data-left-col>
        {/* Map area */}
        <div className="flex-1 relative min-h-0">
          <InteractiveMap
            dark={dark}
            flyToCenter={flyTo?.center}
            flyToZoom={flyTo?.zoom}
            selectedPropertyGeometry={selectedGeometry}
            onPropertyClick={handlePropertyClick}
            showBioLayer={layers.biodiversity.active}
            constraintMapData={constraintMapData}
            sitePlanData={sitePlanData}
            comparisonData={comparisonData}
            onMapReady={handleMapReady}
          />
          <LayerControl layers={layers} onToggle={toggleLayer} position="top-left" />
        </div>

        {/* Horizontal resize handle (only when property selected) */}
        {hasProperty && <HorizontalResizeHandle onDrag={handleHudHeightDrag} />}

        {/* Command HUD at bottom */}
        <div
          className="shrink-0"
          style={hasProperty ? { height: `${hudHeight}px` } : undefined}
        >
          <CommandHUD
            propertyId={selectedPropertyId}
            onClose={handleClose}
            onShowSitePlan={setSitePlanData}
            onShowConstraintMap={setConstraintMapData}
          />
        </div>
      </div>

      {/* Vertical resize handle + Right details panel (only when property selected) */}
      {hasProperty && (
        <>
          <VerticalResizeHandle onDrag={handleDetailsWidthDrag} />
          <div
            className="shrink-0 overflow-hidden bg-white dark:bg-gray-900"
            style={{ width: `${detailsWidth}px` }}
          >
            <PropertySidebar
              propertyId={selectedPropertyId}
              mapRef={mapInstanceRef}
              onClose={handleClose}
              onShowConstraintMap={setConstraintMapData}
              onShowSitePlan={setSitePlanData}
              onShowComparison={setComparisonData}
              onAIAnalyze={() => navigate('/ai')}
            />
          </div>
        </>
      )}
    </div>
  );
}
