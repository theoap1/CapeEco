import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { MapPin, BarChart3, FileText, Map, TrendingUp, Loader2, ExternalLink, Download } from 'lucide-react';
import { MapContainer, TileLayer, GeoJSON, Marker, useMap } from 'react-leaflet';
import L from 'leaflet';
import { GreenStarRadar, CrimeBarChart, StageImpactChart, HealthGauge } from '../AnalysisCharts';
import { getPropertyReport } from '../../utils/api';
import 'leaflet/dist/leaflet.css';

// Fix leaflet default marker icon
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

const CONTEXT_TABS = [
  { id: 'property', label: 'Property', icon: MapPin },
  { id: 'data', label: 'Analysis', icon: BarChart3 },
  { id: 'charts', label: 'Charts', icon: TrendingUp },
  { id: 'map', label: 'Map', icon: Map },
  { id: 'report', label: 'Report', icon: FileText },
];

// ── Property Tab ─────────────────────────────────────────────────────
function PropertyContext({ data }) {
  if (!data?.property) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-600 text-sm px-6 text-center">
        <MapPin className="w-8 h-8 text-gray-700 mb-3" />
        <p>Property data will appear here when you ask about a property.</p>
      </div>
    );
  }

  const p = data.property;
  return (
    <div className="p-4 space-y-3">
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-white mb-3">
          {p.full_address || `ERF ${p.erf_number}`}
        </h3>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {[
            ['Area', p.area_sqm ? `${Number(p.area_sqm).toLocaleString()} m\u00B2` : 'N/A'],
            ['Zoning', p.zoning_primary || 'N/A'],
            ['Suburb', p.suburb || 'N/A'],
            ['Urban Edge', p.inside_urban_edge ? 'Inside' : 'Outside'],
          ].map(([label, value]) => (
            <div key={label} className="bg-gray-900/50 rounded-lg p-2">
              <div className="text-gray-500">{label}</div>
              <div className="text-gray-200 font-medium">{value}</div>
            </div>
          ))}
        </div>
      </div>

      {p.valuation && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Valuation</h4>
          <div className="text-xl font-bold text-ocean-400 font-data">
            R {Number(p.valuation.market_value || p.valuation.total_value || 0).toLocaleString()}
          </div>
          {p.valuation.land_value && (
            <div className="text-xs text-gray-500 mt-1">
              Land: R {Number(p.valuation.land_value).toLocaleString()}
            </div>
          )}
        </div>
      )}

      {data.biodiversity && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Biodiversity</h4>
          {data.biodiversity.map((b, i) => (
            <div key={i} className="flex items-center justify-between py-1 text-xs">
              <span className="text-gray-300">{b.cba_category}</span>
              <span className="text-gray-500">{b.overlap_pct?.toFixed(1)}% overlap</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Analysis Tab ─────────────────────────────────────────────────────
function AnalysisContext({ data }) {
  if (!data?.analysis) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-600 text-sm px-6 text-center">
        <BarChart3 className="w-8 h-8 text-gray-700 mb-3" />
        <p>Analysis results will appear here when the AI runs tools.</p>
      </div>
    );
  }

  const a = data.analysis;
  return (
    <div className="p-4 space-y-3">
      {a.netzero && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Net Zero Scorecard</h4>
          <div className="flex items-baseline gap-2 mb-1">
            <div className="text-2xl font-bold text-ocean-400">{a.netzero.greenstar_rating || 'N/A'}</div>
            <div className="text-xs text-gray-500">Score: {a.netzero.total_score}/100</div>
          </div>
          {a.netzero.categories && (
            <div className="mt-2 space-y-1">
              {a.netzero.categories.map((c, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="text-gray-400">{c.category}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                      <div className="h-full bg-ocean-500 rounded-full" style={{ width: `${(c.score / c.max) * 100}%` }} />
                    </div>
                    <span className="text-gray-300 font-data w-8 text-right">{c.score}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {a.solar && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Solar Potential</h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-gray-900/50 rounded-lg p-2">
              <div className="text-gray-500">System Size</div>
              <div className="text-gray-200 font-medium font-data">{a.solar.system_size_kwp} kWp</div>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-2">
              <div className="text-gray-500">Annual Gen.</div>
              <div className="text-gray-200 font-medium font-data">{Number(a.solar.annual_generation_kwh).toLocaleString()} kWh</div>
            </div>
            {a.solar.payback_years && (
              <div className="bg-gray-900/50 rounded-lg p-2">
                <div className="text-gray-500">Payback</div>
                <div className="text-gray-200 font-medium font-data">{a.solar.payback_years} yrs</div>
              </div>
            )}
            {a.solar.monthly_savings_zar && (
              <div className="bg-gray-900/50 rounded-lg p-2">
                <div className="text-gray-500">Monthly Savings</div>
                <div className="text-green-400 font-medium font-data">R {Number(a.solar.monthly_savings_zar).toLocaleString()}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {a.crime && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Crime Risk</h4>
          <div className="flex items-center gap-3 mb-2">
            <div className={`text-2xl font-bold font-data ${
              a.crime.risk_level === 'Critical' ? 'text-red-400' :
              a.crime.risk_level === 'High' ? 'text-orange-400' :
              a.crime.risk_level === 'Medium' ? 'text-yellow-400' : 'text-green-400'
            }`}>
              {a.crime.risk_score ?? 'N/A'}
            </div>
            <div className="text-xs">
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                a.crime.risk_level === 'Critical' ? 'bg-red-900/40 text-red-400' :
                a.crime.risk_level === 'High' ? 'bg-orange-900/40 text-orange-400' :
                a.crime.risk_level === 'Medium' ? 'bg-yellow-900/40 text-yellow-400' : 'bg-green-900/40 text-green-400'
              }`}>
                {a.crime.risk_level || 'Unknown'}
              </span>
            </div>
          </div>
          {a.crime.station_name && (
            <div className="text-xs text-gray-500">Station: <span className="text-gray-300">{a.crime.station_name}</span></div>
          )}
        </div>
      )}

      {a.loadshedding && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Load Shedding</h4>
          <div className="text-xs text-gray-300 space-y-1">
            <div>Block: <span className="font-data font-medium">{a.loadshedding.block || 'Unknown'}</span></div>
            {a.loadshedding.risk_level && (
              <div>Risk: <span className={`font-medium ${
                a.loadshedding.risk_level === 'High' ? 'text-red-400' :
                a.loadshedding.risk_level === 'Medium' ? 'text-yellow-400' : 'text-green-400'
              }`}>{a.loadshedding.risk_level}</span></div>
            )}
            {a.loadshedding.baseline_impact && (
              <div className="text-gray-500">Impact: <span className="text-gray-300 font-data">{a.loadshedding.baseline_impact}</span></div>
            )}
          </div>
        </div>
      )}

      {a.municipal && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Municipal Health</h4>
          <HealthGauge score={a.municipal.health_score} label="Health Score" />
          {a.municipal.municipality && (
            <div className="text-xs text-gray-500 mt-2">{a.municipal.municipality}</div>
          )}
        </div>
      )}

      {a.biodiversity && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Biodiversity Offset</h4>
          {a.biodiversity.offset_required != null && (
            <div className="text-xs text-gray-300 space-y-1">
              <div>Offset required: <span className={`font-medium ${a.biodiversity.offset_required ? 'text-amber-400' : 'text-green-400'}`}>
                {a.biodiversity.offset_required ? 'Yes' : 'No'}
              </span></div>
              {a.biodiversity.offset_area_ha && (
                <div>Area: <span className="font-data">{a.biodiversity.offset_area_ha.toFixed(2)} ha</span></div>
              )}
              {a.biodiversity.estimated_cost_zar && (
                <div>Est. cost: <span className="font-data text-amber-400">R {Number(a.biodiversity.estimated_cost_zar).toLocaleString()}</span></div>
              )}
            </div>
          )}
          {a.biodiversity.no_go_zones?.length > 0 && (
            <div className="mt-2 px-2 py-1.5 bg-red-900/20 border border-red-800/30 rounded-lg text-xs text-red-400">
              No-go zones detected
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Charts Tab ───────────────────────────────────────────────────────

// Transform netzero scores dict → radar chart array
const NETZERO_MAXES = { energy: 35, water: 25, ecology: 20, location: 10, materials_innovation: 10 };
const NETZERO_LABELS = { energy: 'Energy', water: 'Water', ecology: 'Ecology', location: 'Location', materials_innovation: 'Materials' };

function netzeroToRadar(scores) {
  if (!scores || typeof scores !== 'object') return null;
  return Object.entries(scores)
    .filter(([k]) => NETZERO_MAXES[k])
    .map(([k, v]) => ({ category: NETZERO_LABELS[k] || k, score: v, max: NETZERO_MAXES[k] }));
}

// Transform loadshedding stage_impacts dict → array for StageImpactChart
function stageImpactsToArray(impacts) {
  if (!impacts) return null;
  if (Array.isArray(impacts)) return impacts;
  return Object.entries(impacts)
    .filter(([k]) => k.startsWith('stage_'))
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => ({ stage: parseInt(k.replace('stage_', '')), hours_per_day: v?.hours_per_day || 0 }));
}

// Transform municipal indicators dict → bar-compatible array
function municipalIndicatorsToArray(indicators) {
  if (!indicators || typeof indicators !== 'object') return null;
  return Object.entries(indicators).map(([, v]) => ({
    name: v.label?.replace(/\s*\(.*\)/, '') || '',
    score: v.score || 0,
  }));
}

// Simple inline horizontal bar for small datasets
function MiniHBarChart({ data, valueKey = 'value', labelKey = 'name', colorFn }) {
  if (!data?.length) return null;
  const maxVal = Math.max(...data.map(d => d[valueKey] || 0), 1);
  return (
    <div className="space-y-1.5">
      {data.map((d, i) => {
        const val = d[valueKey] || 0;
        const pct = (val / maxVal) * 100;
        const color = colorFn ? colorFn(val, i) : '#3b98f5';
        return (
          <div key={i}>
            <div className="flex items-center justify-between text-[10px] mb-0.5">
              <span className="text-gray-400 truncate mr-2">{d[labelKey]}</span>
              <span className="text-gray-300 font-data shrink-0">{typeof val === 'number' && val > 1000 ? `${(val/1000).toFixed(0)}k` : val?.toFixed?.(1) ?? val}</span>
            </div>
            <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// CBA severity colors
const CBA_CHART_COLORS = {
  'PA': '#dc2626', 'CA': '#ef4444', 'CBA 1a': '#f97316', 'CBA 1b': '#fb923c',
  'CBA 1c': '#fbbf24', 'CBA 2': '#facc15', 'ESA 1': '#a3e635', 'ESA 2': '#4ade80', 'ONA': '#22d3ee',
};

function ChartsContext({ data }) {
  const a = data?.analysis;
  const bio = data?.biodiversity;
  const property = data?.property;

  // Build list of available chart sections
  const charts = [];

  // 1. Biodiversity overlaps from property context
  if (bio?.length > 0) {
    charts.push(
      <div key="bio" className="bg-gray-800 border border-gray-700 rounded-xl p-4">
        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Biodiversity Overlaps</h4>
        <MiniHBarChart
          data={bio.map(b => ({ name: b.cba_category, value: b.overlap_pct || 0 }))}
          colorFn={(_, i) => CBA_CHART_COLORS[bio[i]?.cba_category] || '#3b98f5'}
        />
      </div>
    );
  }

  // 2. Netzero radar (transform scores dict → array)
  if (a?.netzero?.scores) {
    const radarData = netzeroToRadar(a.netzero.scores);
    if (radarData?.length) {
      charts.push(
        <div key="netzero" className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
            Green Star — {a.netzero.greenstar_rating || 'N/A'}
          </h4>
          <div className="text-[10px] text-gray-500 mb-2">Score: {a.netzero.total_score}/100</div>
          <GreenStarRadar data={radarData} />
        </div>
      );
    }
  }

  // 3. Solar & water summary
  if (a?.netzero?.solar_summary || a?.solar) {
    const solar = a.netzero?.solar_summary || a.solar;
    const water = a.netzero?.water_summary || a.water;
    const items = [];
    if (solar?.system_kwp || solar?.system_size_kwp) items.push({ name: 'System Size (kWp)', value: solar.system_kwp || solar.system_size_kwp });
    if (solar?.annual_kwh || solar?.annual_generation_kwh) items.push({ name: 'Annual Gen. (MWh)', value: ((solar.annual_kwh || solar.annual_generation_kwh) / 1000) });
    if (solar?.netzero_ratio) items.push({ name: 'Net Zero Ratio', value: solar.netzero_ratio * 100 });
    if (solar?.carbon_offset_tonnes) items.push({ name: 'CO₂ Offset (t)', value: solar.carbon_offset_tonnes });
    if (water?.annual_harvest_kl) items.push({ name: 'Rainwater (kL/yr)', value: water.annual_harvest_kl });
    if (water?.demand_met_pct) items.push({ name: 'Demand Met (%)', value: water.demand_met_pct });
    if (items.length) {
      charts.push(
        <div key="solar" className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Energy & Water</h4>
          <MiniHBarChart data={items} colorFn={(v) => v >= 50 ? '#22c55e' : '#3b98f5'} />
        </div>
      );
    }
  }

  // 4. Crime categories
  if (a?.crime?.top_categories?.length > 0) {
    charts.push(
      <div key="crime" className="bg-gray-800 border border-gray-700 rounded-xl p-4">
        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Top Crime Categories</h4>
        <CrimeBarChart data={a.crime.top_categories} maxItems={6} />
      </div>
    );
  }

  // 5. Load shedding stages (transform dict → array)
  if (a?.loadshedding?.stage_impacts) {
    const stageData = stageImpactsToArray(a.loadshedding.stage_impacts);
    if (stageData?.length) {
      charts.push(
        <div key="loadshed" className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Load Shedding by Stage</h4>
          <StageImpactChart data={stageData} />
        </div>
      );
    }
  }

  // 6. Municipal health indicators
  if (a?.municipal) {
    const score = a.municipal.overall_score ?? a.municipal.health_score;
    const indicators = municipalIndicatorsToArray(a.municipal.indicators);
    if (score != null || indicators?.length) {
      charts.push(
        <div key="municipal" className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Municipal Health</h4>
          {score != null && <HealthGauge score={score} label="Overall Score" />}
          {indicators?.length > 0 && (
            <div className="mt-3">
              <MiniHBarChart
                data={indicators}
                valueKey="score"
                labelKey="name"
                colorFn={(v) => v >= 70 ? '#22c55e' : v >= 50 ? '#f59e0b' : '#ef4444'}
              />
            </div>
          )}
        </div>
      );
    }
  }

  // 7. Comparison valuations
  if (a?.comparison) {
    const comp = a.comparison;
    const radius = comp.radius;
    const suburb = comp.suburb;
    const items = [];

    // Build comparison stats chart
    const src = radius || suburb;
    if (src?.stats) {
      items.push({ name: 'Minimum', value: src.stats.min_value || 0 });
      items.push({ name: 'Median', value: src.stats.median_value || 0 });
      items.push({ name: 'Mean', value: src.stats.mean_value || 0 });
      items.push({ name: 'Maximum', value: src.stats.max_value || 0 });
    }
    if (src?.selected_property?.market_value_zar) {
      items.push({ name: 'This Property', value: src.selected_property.market_value_zar });
    }

    if (items.length) {
      charts.push(
        <div key="comparison" className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Property Valuations</h4>
          <div className="text-[10px] text-gray-500 mb-3">
            {src?.count || 0} properties compared {radius ? `within ${radius.radius_km || '?'}km` : 'in suburb'}
          </div>
          <MiniHBarChart
            data={items.map(d => ({ name: d.name, value: d.value / 1000000 }))}
            colorFn={(_, i) => i === items.length - 1 ? '#3b98f5' : '#6b7280'}
          />
          <div className="text-[9px] text-gray-600 mt-1 text-right">Values in millions (ZAR)</div>
        </div>
      );
    }
  }

  // 8. Biodiversity offset analysis
  if (a?.biodiversity && !a.biodiversity.error) {
    const b = a.biodiversity;
    const offsetItems = [];
    if (b.overlaps?.length) {
      b.overlaps.forEach(o => {
        offsetItems.push({ name: o.cba_category || 'Unknown', value: o.overlap_pct || 0 });
      });
    }
    if (b.offset_area_ha) offsetItems.push({ name: 'Offset Required (ha)', value: b.offset_area_ha });
    if (b.offset_ratio) offsetItems.push({ name: 'Offset Ratio', value: b.offset_ratio });

    if (offsetItems.length) {
      charts.push(
        <div key="biooffset" className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Biodiversity Offset</h4>
          <MiniHBarChart
            data={offsetItems}
            colorFn={(v) => v > 5 ? '#ef4444' : v > 1 ? '#f59e0b' : '#22c55e'}
          />
        </div>
      );
    }
  }

  // 9. Property area as a simple stat when nothing else is available
  if (charts.length === 0 && property) {
    const items = [];
    if (property.area_sqm) items.push({ name: 'Property Area (m²)', value: property.area_sqm });
    if (property.valuation?.market_value_zar) items.push({ name: 'Market Value (R)', value: property.valuation.market_value_zar / 1000 });

    if (items.length) {
      charts.push(
        <div key="property-stats" className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Property Overview</h4>
          <div className="grid grid-cols-2 gap-3">
            {property.area_sqm && (
              <div className="text-center">
                <div className="text-2xl font-bold text-ocean-400 font-data">{Number(property.area_sqm).toLocaleString()}</div>
                <div className="text-[10px] text-gray-500 mt-0.5">Area (m²)</div>
              </div>
            )}
            {property.valuation?.market_value_zar && (
              <div className="text-center">
                <div className="text-2xl font-bold text-green-400 font-data">R{(property.valuation.market_value_zar / 1000000).toFixed(1)}M</div>
                <div className="text-[10px] text-gray-500 mt-0.5">Market Value</div>
              </div>
            )}
          </div>
          {property.zoning_primary && (
            <div className="mt-3 px-2 py-1.5 bg-gray-900/50 rounded-lg text-center">
              <div className="text-[10px] text-gray-500">Zoning</div>
              <div className="text-xs text-gray-300 font-medium">{property.zoning_primary}</div>
            </div>
          )}
        </div>
      );
    }
  }

  if (charts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-600 text-sm px-6 text-center">
        <TrendingUp className="w-8 h-8 text-gray-700 mb-3" />
        <p>Charts will appear here when data is available.</p>
        <p className="text-xs text-gray-700 mt-2">Ask the AI to analyze a property to see visualizations.</p>
      </div>
    );
  }

  return <div className="p-4 space-y-4">{charts}</div>;
}

// ── Map Tab ──────────────────────────────────────────────────────────
function FitBounds({ geometry }) {
  const map = useMap();
  useEffect(() => {
    if (!geometry) return;
    try {
      const geoLayer = L.geoJSON(geometry);
      const bounds = geoLayer.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [30, 30], maxZoom: 17 });
      }
    } catch { /* ignore invalid geometry */ }
  }, [geometry, map]);
  return null;
}

function MapContext({ data }) {
  const property = data?.property;
  const hasLocation = property && (property.centroid_lat || property.geometry);

  if (!hasLocation) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-600 text-sm px-6 text-center">
        <Map className="w-8 h-8 text-gray-700 mb-3" />
        <p>Map will show property location when you ask about a property.</p>
      </div>
    );
  }

  const center = [
    property.centroid_lat || -33.9249,
    property.centroid_lon || 18.4241,
  ];

  const geojsonStyle = {
    color: '#3b98f5',
    weight: 2,
    fillColor: '#3b98f5',
    fillOpacity: 0.15,
  };

  // Constraint map overlay
  const constraintMap = data?.constraintMap;

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 relative">
        <MapContainer
          center={center}
          zoom={16}
          className="h-full w-full"
          zoomControl={false}
          attributionControl={false}
          style={{ background: '#1a1a2e' }}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            maxZoom={19}
          />
          {property.geometry && (
            <>
              <GeoJSON
                key={property.id || JSON.stringify(property.geometry).slice(0, 50)}
                data={{ type: 'Feature', geometry: property.geometry, properties: {} }}
                style={geojsonStyle}
              />
              <FitBounds geometry={{ type: 'Feature', geometry: property.geometry }} />
            </>
          )}
          {!property.geometry && (
            <>
              <Marker position={center} />
              <FitBounds geometry={{ type: 'Point', coordinates: [center[1], center[0]] }} />
            </>
          )}
          {constraintMap?.features && (
            <GeoJSON
              key={`constraint-${constraintMap.features.length}`}
              data={constraintMap}
              style={(feature) => ({
                color: feature.properties?.color || '#ef4444',
                weight: 1.5,
                fillColor: feature.properties?.color || '#ef4444',
                fillOpacity: 0.25,
              })}
            />
          )}
        </MapContainer>
      </div>
      <div className="p-3 bg-gray-900/80 border-t border-gray-800">
        <div className="text-xs text-gray-400">
          {property.full_address || `ERF ${property.erf_number}, ${property.suburb || ''}`}
        </div>
        {property.area_sqm && (
          <div className="text-[10px] text-gray-600 mt-0.5">
            {Number(property.area_sqm).toLocaleString()} m\u00B2
          </div>
        )}
      </div>
    </div>
  );
}

// ── Report Tab ───────────────────────────────────────────────────────
function ReportContext({ data }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const property = data?.property;

  const loadReport = useCallback(async () => {
    if (!property?.id) return;
    setLoading(true);
    setError(null);
    try {
      const r = await getPropertyReport(property.id);
      setReport(r);
    } catch (e) {
      setError(e.message || 'Failed to load report');
    } finally {
      setLoading(false);
    }
  }, [property?.id]);

  // Auto-load report when property changes
  useEffect(() => {
    if (property?.id) {
      loadReport();
    } else {
      setReport(null);
    }
  }, [property?.id, loadReport]);

  if (!property) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-600 text-sm px-6 text-center">
        <FileText className="w-8 h-8 text-gray-700 mb-3" />
        <p>Ask about a property to see its development report here.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-500">
        <Loader2 className="w-6 h-6 animate-spin mb-2" />
        <span className="text-xs">Loading report...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-600 text-sm px-6 text-center">
        <p className="text-red-400 mb-3">Could not load report</p>
        <button onClick={loadReport} className="text-xs text-ocean-400 hover:text-ocean-300 underline">
          Retry
        </button>
      </div>
    );
  }

  if (!report) return null;

  const r = report;
  const fmtZar = (v) => v != null ? `R ${Number(v).toLocaleString('en-ZA')}` : '\u2014';

  return (
    <div className="p-4 space-y-3 text-xs">
      {/* Header */}
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-2">
          <FileText className="w-4 h-4 text-ocean-400" />
          <h3 className="text-sm font-semibold text-white">Development Report</h3>
        </div>
        <div className="text-gray-300">{r.property?.full_address || `ERF ${r.property?.erf_number}`}</div>
        <div className="text-gray-600 text-[10px] mt-1">
          {r.property?.suburb} &middot; {r.property?.area_sqm ? `${Number(r.property.area_sqm).toLocaleString()} m\u00B2` : ''}
        </div>
      </div>

      {/* Risk Summary */}
      {r.risk_summary && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Risk Summary</h4>
          <div className="grid grid-cols-2 gap-2">
            {r.risk_summary.biodiversity_risk && (
              <RiskBadge label="Biodiversity" level={r.risk_summary.biodiversity_risk} />
            )}
            {r.risk_summary.heritage_risk && (
              <RiskBadge label="Heritage" level={r.risk_summary.heritage_risk} />
            )}
            {r.risk_summary.urban_edge && (
              <div className="bg-gray-900/50 rounded-lg p-2">
                <div className="text-gray-500">Urban Edge</div>
                <div className={`font-medium ${r.risk_summary.urban_edge === 'Inside' ? 'text-green-400' : 'text-amber-400'}`}>
                  {r.risk_summary.urban_edge}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Valuation */}
      {r.valuation && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Valuation</h4>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-gray-500">Market Value</span>
              <span className="text-gray-200 font-data">{fmtZar(r.valuation.market_value)}</span>
            </div>
            {r.valuation.land_value && (
              <div className="flex justify-between">
                <span className="text-gray-500">Land Value</span>
                <span className="text-gray-200 font-data">{fmtZar(r.valuation.land_value)}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Net Zero */}
      {r.netzero?.scorecard && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4">
          <h4 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Net Zero</h4>
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold text-ocean-400">{r.netzero.scorecard.greenstar_rating}</span>
            <span className="text-gray-500">({r.netzero.scorecard.total_score}/100)</span>
          </div>
        </div>
      )}

      {/* Open full report */}
      <button
        onClick={() => {
          if (property?.id) window.open(`/map?property=${property.id}&report=true`, '_blank');
        }}
        className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-ocean-600/20 border border-ocean-500/30
                   rounded-lg text-ocean-400 hover:bg-ocean-600/30 transition-colors text-xs font-medium"
      >
        <ExternalLink className="w-3.5 h-3.5" />
        Open Full Report
      </button>
    </div>
  );
}

function RiskBadge({ label, level }) {
  const colors = {
    Critical: 'text-red-400 bg-red-900/30',
    High: 'text-orange-400 bg-orange-900/30',
    Medium: 'text-yellow-400 bg-yellow-900/30',
    Low: 'text-green-400 bg-green-900/30',
  };
  return (
    <div className="bg-gray-900/50 rounded-lg p-2">
      <div className="text-gray-500">{label}</div>
      <div className={`font-medium ${colors[level] || 'text-gray-300'}`}>{level}</div>
    </div>
  );
}

// ── Resize Handle ────────────────────────────────────────────────────
function ResizeHandle({ onDrag }) {
  const isDragging = useRef(false);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMouseMove = (e) => {
      if (isDragging.current) onDrag(e.clientX);
    };
    const onMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [onDrag]);

  return (
    <div
      onMouseDown={handleMouseDown}
      className="w-1.5 cursor-col-resize group flex items-center justify-center shrink-0 hover:bg-ocean-500/20 transition-colors"
    >
      <div className="w-0.5 h-8 bg-gray-700 rounded-full group-hover:bg-ocean-500 transition-colors" />
    </div>
  );
}

// ── Main Panel ───────────────────────────────────────────────────────
export default function ContextPanel({ data, activeTab, onTabChange, width, onWidthChange }) {
  const panelRef = useRef(null);

  const handleDrag = useCallback((clientX) => {
    if (!panelRef.current) return;
    const parentRect = panelRef.current.parentElement.getBoundingClientRect();
    const newWidth = parentRect.right - clientX;
    const clamped = Math.max(280, Math.min(700, newWidth));
    onWidthChange(clamped);
  }, [onWidthChange]);

  return (
    <>
      <ResizeHandle onDrag={handleDrag} />
      <div
        ref={panelRef}
        className="flex flex-col shrink-0 hidden lg:flex"
        style={{ width: `${width}px` }}
      >
        {/* Tab bar */}
        <div className="h-10 border-b border-gray-800 flex items-center px-1 gap-0.5 shrink-0 overflow-x-auto">
          {CONTEXT_TABS.map(tab => {
            const Icon = tab.icon;
            const isActive = tab.id === activeTab;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`flex items-center gap-1 px-2 py-1.5 rounded-md text-[11px] font-medium transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-gray-800 text-white'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                <Icon className="w-3 h-3" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === 'property' && <PropertyContext data={data} />}
          {activeTab === 'data' && <AnalysisContext data={data} />}
          {activeTab === 'charts' && <ChartsContext data={data} />}
          {activeTab === 'map' && <MapContext data={data} />}
          {activeTab === 'report' && <ReportContext data={data} />}
        </div>
      </div>
    </>
  );
}
