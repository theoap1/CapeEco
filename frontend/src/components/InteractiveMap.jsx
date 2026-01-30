import { useEffect, useRef, useCallback, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { CT_CENTER, CT_ZOOM, CBA_COLORS } from '../utils/constants';
import { getBiodiversityLayer, getPropertiesLayer } from '../utils/api';

// Fix Leaflet default icon issue with bundlers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// Tile layer configs — all free, no API key
const TILE_LAYERS = {
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    label: 'Streets',
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, Maxar, Earthstar Geographics',
    label: 'Satellite',
  },
  topo: {
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenTopoMap',
    label: 'Terrain',
  },
};

function MapEvents({ onPropertyClick, onMoveEnd }) {
  useMapEvents({
    moveend: (e) => {
      const map = e.target;
      const b = map.getBounds();
      onMoveEnd({
        west: b.getWest(),
        south: b.getSouth(),
        east: b.getEast(),
        north: b.getNorth(),
        zoom: map.getZoom(),
      });
    },
  });
  return null;
}

function FlyTo({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center) {
      map.flyTo(center, zoom || 17, { duration: 1.5 });
    }
  }, [center, zoom, map]);
  return null;
}

// Selected property highlight
function SelectedPropertyLayer({ geojson }) {
  const map = useMap();
  const layerRef = useRef(null);

  useEffect(() => {
    if (layerRef.current) {
      map.removeLayer(layerRef.current);
    }
    if (geojson) {
      layerRef.current = L.geoJSON(geojson, {
        style: {
          color: '#3b98f5',
          weight: 3,
          fillColor: '#3b98f5',
          fillOpacity: 0.15,
          dashArray: '',
        },
      }).addTo(map);
    }
    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
      }
    };
  }, [geojson, map]);

  return null;
}

export default function InteractiveMap({
  dark,
  flyToCenter,
  flyToZoom,
  selectedPropertyGeometry,
  onPropertyClick,
  showBioLayer,
  constraintMapData,
}) {
  const [baseLayer, setBaseLayer] = useState('osm');
  const [bioData, setBioData] = useState(null);
  const [propertiesData, setPropertiesData] = useState(null);
  const fetchingRef = useRef(false);

  const handleMoveEnd = useCallback(async (viewport) => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;

    try {
      if (showBioLayer) {
        const bio = await getBiodiversityLayer(viewport);
        setBioData(bio);
      }
      if (viewport.zoom >= 16) {
        const props = await getPropertiesLayer(viewport);
        setPropertiesData(props);
      } else {
        setPropertiesData(null);
      }
    } catch (err) {
      console.error('Layer fetch error:', err);
    } finally {
      fetchingRef.current = false;
    }
  }, [showBioLayer]);

  const bioStyle = useCallback((feature) => {
    const cat = feature.properties.cba_category;
    const c = CBA_COLORS[cat] || { fill: '#9ca3af', stroke: '#6b7280' };
    return {
      fillColor: c.fill,
      color: c.stroke,
      weight: 1,
      fillOpacity: 0.35,
    };
  }, []);

  const propertyStyle = {
    color: '#6b7280',
    weight: 1,
    fillColor: 'transparent',
    fillOpacity: 0,
  };

  const constraintStyle = useCallback((feature) => {
    const layer = feature.properties.layer;
    switch (layer) {
      case 'property_boundary':
        return { color: '#3b98f5', weight: 2.5, fillOpacity: 0, dashArray: '6 3' };
      case 'cba_overlay':
        return bioStyle(feature);
      case 'buffer_zone':
        return { color: '#f97316', weight: 1.5, fillColor: '#f97316', fillOpacity: 0.2, dashArray: '4 4' };
      case 'developable_area':
        return { color: '#22c55e', weight: 2, fillColor: '#22c55e', fillOpacity: 0.15 };
      case 'ecosystem_type':
        return { color: '#8b5cf6', weight: 1, fillColor: '#8b5cf6', fillOpacity: 0.1 };
      default:
        return { color: '#9ca3af', weight: 1, fillOpacity: 0.1 };
    }
  }, [bioStyle]);

  const onEachProperty = useCallback((feature, layer) => {
    layer.on('click', () => {
      onPropertyClick?.(feature.properties);
    });
    layer.bindTooltip(
      `ERF ${feature.properties.erf_number || '?'}<br/>${feature.properties.suburb || ''}`,
      { sticky: true, className: 'text-xs' }
    );
  }, [onPropertyClick]);

  const tile = TILE_LAYERS[baseLayer];

  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={CT_CENTER}
        zoom={CT_ZOOM}
        className="h-full w-full z-0"
        zoomControl={false}
      >
        <TileLayer url={tile.url} attribution={tile.attribution} maxZoom={19} />

        <MapEvents onPropertyClick={onPropertyClick} onMoveEnd={handleMoveEnd} />

        {flyToCenter && <FlyTo center={flyToCenter} zoom={flyToZoom} />}

        {selectedPropertyGeometry && (
          <SelectedPropertyLayer geojson={selectedPropertyGeometry} />
        )}

        {showBioLayer && bioData && bioData.features?.length > 0 && (
          <GeoJSON
            key={JSON.stringify(bioData).slice(0, 100)}
            data={bioData}
            style={bioStyle}
            onEachFeature={(feature, layer) => {
              const cat = feature.properties.cba_category;
              const c = CBA_COLORS[cat];
              layer.bindTooltip(c?.label || cat, { sticky: true });
            }}
          />
        )}

        {propertiesData && propertiesData.features?.length > 0 && (
          <GeoJSON
            key={'props-' + propertiesData.features.length}
            data={propertiesData}
            style={propertyStyle}
            onEachFeature={onEachProperty}
          />
        )}

        {constraintMapData && constraintMapData.features?.length > 0 && (
          <GeoJSON
            key={'constraint-' + JSON.stringify(constraintMapData).slice(0, 50)}
            data={constraintMapData}
            style={constraintStyle}
            onEachFeature={(feature, layer) => {
              const p = feature.properties;
              layer.bindTooltip(p.layer?.replace('_', ' ') || '', { sticky: true });
            }}
          />
        )}
      </MapContainer>

      {/* Base layer switcher */}
      <div className="absolute top-3 right-3 z-[1000] flex gap-1 bg-white/90 dark:bg-gray-800/90
                      backdrop-blur rounded-lg shadow-md p-1">
        {Object.entries(TILE_LAYERS).map(([key, val]) => (
          <button
            key={key}
            onClick={() => setBaseLayer(key)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors
                       ${baseLayer === key
                         ? 'bg-ocean-600 text-white'
                         : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'}`}
          >
            {val.label}
          </button>
        ))}
      </div>
    </div>
  );
}
