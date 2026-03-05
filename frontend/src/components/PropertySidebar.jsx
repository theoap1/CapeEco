import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X, ChevronRight, Sun, Droplets, Leaf, MapPin, Building, Ruler,
  Zap, Star, AlertTriangle, Shield, TrendingUp, Info, FileText,
  Search, DollarSign, Hammer, Siren, BatteryCharging, Landmark, MessageSquare, Loader2, ExternalLink,
} from 'lucide-react';
import { getProperty, getNetZeroAnalysis, getBiodiversityAnalysis, getConstraintMap, getSitePlan, getMassing, getPropertyReport, getRadiusComparison, getSuburbComparison, getConstructionCost, getLoadshedding, getCrimeRisk, getMunicipalHealth, getDevelopmentPotential } from '../utils/api';
import { captureMapImage } from '../utils/captureMap';
import ReportView from './ReportView';
import SANSComplianceReport from './SANSComplianceReport';
import SiteAnalysisReport from './SiteAnalysisReport';
import { CBA_COLORS, BIO_STATUS, GREENSTAR_COLORS, RISK_LEVEL_CONFIG, STAGE_COLORS, getMuniHealthLevel, MUNI_HEALTH_COLORS } from '../utils/constants';
import { GreenStarRadar, CrimeBarChart, StageImpactChart, HealthGauge } from './AnalysisCharts';

// Heritage category descriptions (CCT Heritage Resources Audit)
const HERITAGE_CATEGORIES = {
  '0': 'Demolished / not found',
  '1': 'Individual landmark',
  '2': 'Heritage area contributor',
  '3': 'Streetscape contributor',
  '4': 'Contextual contributor',
  '5': 'Neutral / no heritage value',
};

const CITY_GRADINGS = {
  'I': 'Grade I — National significance',
  'II': 'Grade II — Provincial significance',
  'III': 'Grade III — Local significance (may not be demolished without permit)',
  'IIIA': 'Grade IIIA — Worthy of conservation',
  'IIIB': 'Grade IIIB — Contributes to heritage area',
  'IIIC': 'Grade IIIC — Streetscape value only',
  'Not Set': null,
};

// Score category explanations
const SCORE_HELP = {
  energy: 'Rooftop solar generation vs estimated building energy demand (SANS 10400-XA). Multi-storey buildings score lower as roof area serves more floors.',
  water: 'Rainwater harvesting potential vs water demand. Cape Town has 4 rainfall zones (550-1100mm/yr). Winter rainfall pattern means seasonal storage needed.',
  ecology: 'Biodiversity sensitivity of the site. Properties with no CBA/ESA overlay score well. Protected or Critical Biodiversity Areas reduce developability.',
  location: 'Inside the urban edge = existing infrastructure, public transport, lower carbon footprint. Outside = car-dependent, requires costly service extensions.',
  materials_innovation: 'Baseline score for materials and innovation — actual rating depends on design choices (not assessable at screening level).',
};

function Badge({ status }) {
  const s = BIO_STATUS[status] || BIO_STATUS.clear;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${s.color} ${s.text}`}>
      {s.label}
    </span>
  );
}

function ScoreBar({ label, score, max, color, help }) {
  const [showHelp, setShowHelp] = useState(false);
  const pct = Math.min((score / max) * 100, 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center text-xs">
        <span className="text-gray-600 dark:text-gray-400 flex items-center gap-1">
          {label}
          {help && (
            <button
              onClick={() => setShowHelp(!showHelp)}
              className="text-gray-400 hover:text-ocean-500 transition-colors"
            >
              <Info className="w-3 h-3" />
            </button>
          )}
        </span>
        <span className="font-medium text-gray-900 dark:text-gray-100">{score}/{max}</span>
      </div>
      <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      {showHelp && (
        <p className="text-[10px] text-gray-500 dark:text-gray-400 leading-relaxed mt-0.5">{help}</p>
      )}
    </div>
  );
}

function Section({ title, icon: Icon, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-gray-200 dark:border-gray-700">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
      >
        <div className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-gray-100">
          {Icon && <Icon className="w-4 h-4 text-ocean-500" />}
          {title}
        </div>
        <ChevronRight className={`w-4 h-4 text-gray-400 transition-transform ${open ? 'rotate-90' : ''}`} />
      </button>
      {open && <div className="px-4 pb-4 space-y-3">{children}</div>}
    </div>
  );
}

function InfoRow({ label, value, sub }) {
  return (
    <div className="flex justify-between items-start text-sm">
      <span className="text-gray-500 dark:text-gray-400">{label}</span>
      <div className="text-right">
        <span className="font-medium text-gray-900 dark:text-gray-100">{value}</span>
        {sub && <div className="text-xs text-gray-400">{sub}</div>}
      </div>
    </div>
  );
}

function HeritageCard({ h }) {
  const catLabel = HERITAGE_CATEGORIES[h.heritage_category] || `Category ${h.heritage_category}`;
  const grading = CITY_GRADINGS[h.city_grading];
  const isInventory = h.source === 'inventory';

  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2.5 space-y-1">
      <div className="flex items-start justify-between">
        <span className="text-xs font-medium text-gray-900 dark:text-gray-100">
          {h.site_name || (isInventory ? 'Heritage Inventory Record' : 'NHRA Protected Site')}
        </span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
          h.source === 'nhra' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
        }`}>
          {h.source === 'nhra' ? 'NHRA' : 'Inventory'}
        </span>
      </div>
      <div className="text-[11px] text-gray-500 dark:text-gray-400 space-y-0.5">
        <div>{catLabel}</div>
        {grading && <div>{grading}</div>}
        {h.nhra_status && <div>Status: {h.nhra_status}</div>}
        {h.architectural_style && <div>Style: {h.architectural_style}</div>}
        {h.period && <div>Period: {h.period}</div>}
      </div>
    </div>
  );
}

function fmtZar(val) {
  if (val == null) return '\u2014';
  return `R ${Math.round(val).toLocaleString()}`;
}

function ComparisonCard({ label, data, color }) {
  if (!data) return null;
  return (
    <div className={`bg-gray-50 dark:bg-gray-800 rounded-lg p-2.5 border-l-3 ${color}`}>
      <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">{label}</div>
      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{fmtZar(data.market_value_zar)}</div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
        {data.value_per_sqm ? `R ${data.value_per_sqm.toLocaleString()}/m²` : ''}
        {data.area_sqm ? ` \u00b7 ${Math.round(data.area_sqm).toLocaleString()} m²` : ''}
      </div>
      {data.full_address && (
        <div className="text-[10px] text-gray-400 mt-0.5 truncate">{data.full_address}</div>
      )}
      {data.distance_m != null && (
        <div className="text-[10px] text-gray-400">{data.distance_m < 1000 ? `${data.distance_m} m away` : `${(data.distance_m / 1000).toFixed(1)} km away`}</div>
      )}
    </div>
  );
}

export default function PropertySidebar({ propertyId, mapRef, onClose, onShowConstraintMap, onShowSitePlan, onShowComparison, onAIAnalyze }) {
  const navigate = useNavigate();
  const [property, setProperty] = useState(null);
  const [netzero, setNetzero] = useState(null);
  const [biodiversity, setBiodiversity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisRun, setAnalysisRun] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [showSANSReport, setShowSANSReport] = useState(false);
  const [showSiteAnalysis, setShowSiteAnalysis] = useState(false);
  const [mapImage, setMapImage] = useState(null);
  const [capturingMap, setCapturingMap] = useState(null); // 'sans' | 'site' | null
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [radiusData, setRadiusData] = useState(null);
  const [suburbData, setSuburbData] = useState(null);
  const [constructionCost, setConstructionCost] = useState(null);
  const [radiusKm, setRadiusKm] = useState(1.0);
  const [comparisonRun, setComparisonRun] = useState(false);
  const [crimeData, setCrimeData] = useState(null);
  const [loadsheddingData, setLoadsheddingData] = useState(null);
  const [municipalData, setMunicipalData] = useState(null);
  const [devPotential, setDevPotential] = useState(null);

  useEffect(() => {
    if (!propertyId) return;
    setLoading(true);
    setAnalysisRun(false);
    setNetzero(null);
    setBiodiversity(null);
    setComparisonRun(false);
    setRadiusData(null);
    setSuburbData(null);
    setConstructionCost(null);

    getProperty(propertyId)
      .then(setProperty)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [propertyId]);

  useEffect(() => {
    if (!propertyId) return;
    setCrimeData(null);
    setLoadsheddingData(null);
    setMunicipalData(null);
    setDevPotential(null);

    getCrimeRisk(propertyId).then(setCrimeData).catch(() => setCrimeData({ error: 'Failed to load' }));
    getLoadshedding(propertyId).then(setLoadsheddingData).catch(() => setLoadsheddingData({ error: 'Failed to load' }));
    getMunicipalHealth(propertyId).then(setMunicipalData).catch(() => setMunicipalData({ error: 'Failed to load' }));
    getDevelopmentPotential(propertyId).then(setDevPotential).catch(() => setDevPotential({ error: 'Failed to load' }));
  }, [propertyId]);

  const runAnalysis = async () => {
    setAnalysisLoading(true);
    try {
      const [nz, bio] = await Promise.all([
        getNetZeroAnalysis(propertyId),
        getBiodiversityAnalysis(propertyId),
      ]);
      setNetzero(nz);
      setBiodiversity(bio);
      setAnalysisRun(true);
    } catch (err) {
      console.error(err);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const showConstraintMap = async () => {
    try {
      const data = await getConstraintMap(propertyId);
      onShowConstraintMap?.(data);
    } catch (err) {
      console.error(err);
    }
  };

  const [sitePlanLoading, setSitePlanLoading] = useState(false);

  const showSitePlan = async () => {
    setSitePlanLoading(true);
    try {
      const [sp, mass] = await Promise.all([
        getSitePlan(propertyId),
        getMassing(propertyId),
      ]);
      // Merge both GeoJSON FeatureCollections, deduplicate property_boundary
      const spFeatures = sp?.features || [];
      const massFeatures = (mass?.features || []).filter(
        f => f.properties.layer !== 'property_boundary' && f.properties.layer !== 'setback_zone'
      );
      const merged = {
        type: 'FeatureCollection',
        features: [...spFeatures, ...massFeatures],
      };
      onShowSitePlan?.(merged);
    } catch (err) {
      console.error(err);
    } finally {
      setSitePlanLoading(false);
    }
  };

  const runComparison = async () => {
    setComparisonLoading(true);
    try {
      const [radius, suburb, cost] = await Promise.all([
        getRadiusComparison(propertyId, radiusKm),
        getSuburbComparison(propertyId),
        getConstructionCost(propertyId),
      ]);
      setRadiusData(radius);
      setSuburbData(suburb);
      setConstructionCost(cost);
      setComparisonRun(true);
      // Send comparison data to map for visualization
      onShowComparison?.({
        radiusKm,
        center: radius?.selected_property
          ? [radius.selected_property.centroid_lat, radius.selected_property.centroid_lon]
          : null,
        cheapest: radius?.cheapest,
        mostExpensive: radius?.most_expensive,
      });
    } catch (err) {
      console.error('Comparison error:', err);
    } finally {
      setComparisonLoading(false);
    }
  };

  if (!propertyId) return null;

  const bioStatus = (() => {
    if (!property?.biodiversity?.length) return 'clear';
    const top = property.biodiversity[0].cba_category;
    if (['PA', 'CA', 'CBA 1a'].includes(top)) return 'no-go';
    if (['CBA 1b', 'CBA 1c'].includes(top)) return 'exceptional';
    if (['CBA 2', 'ESA 1', 'ESA 2'].includes(top)) return 'offset';
    return 'clear';
  })();

  return (
    <div className="w-full h-full bg-white dark:bg-gray-900 border-l border-gray-200
                    dark:border-gray-700 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between
                      bg-gradient-to-r from-ocean-600 to-ocean-700">
        <h2 className="text-sm font-semibold text-white truncate">Property Details</h2>
        <div className="flex items-center gap-1">
          {onAIAnalyze && (
            <button
              onClick={onAIAnalyze}
              className="flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium
                         bg-white/15 hover:bg-white/25 text-white transition-colors"
              title="Analyze with AI"
            >
              <MessageSquare className="w-3 h-3" />
              Ask AI
            </button>
          )}
          <button onClick={onClose} className="text-white/70 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="w-8 h-8 border-3 border-ocean-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : property ? (
        <div className="flex-1 overflow-y-auto sidebar-scroll">
          {/* Property summary */}
          <div className="px-4 py-4 space-y-3 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-ocean-500" />
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">
                    ERF {property.erf_number}
                  </h3>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 ml-6">
                  {property.full_address || property.suburb}
                </p>
              </div>
              <Badge status={bioStatus} />
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2">
                <div className="text-gray-400">Area</div>
                <div className="font-semibold text-gray-900 dark:text-gray-100">
                  {property.area_sqm ? `${Math.round(property.area_sqm).toLocaleString()} m²` : '\u2014'}
                </div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2">
                <div className="text-gray-400">Zoning</div>
                <div className="font-semibold text-gray-900 dark:text-gray-100 truncate" title={property.zoning_primary}>
                  {property.zoning_primary?.split(':')[0]?.trim() || '\u2014'}
                </div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2">
                <div className="text-gray-400">Urban Edge</div>
                <div className="font-semibold text-gray-900 dark:text-gray-100">
                  {property.inside_urban_edge ? 'Inside' : 'Outside'}
                </div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2">
                <div className="text-gray-400">Suburb</div>
                <div className="font-semibold text-gray-900 dark:text-gray-100 truncate">
                  {property.suburb || '\u2014'}
                </div>
              </div>
            </div>
          </div>

          {/* Risk Summary Strip */}
          {(crimeData || loadsheddingData || municipalData) && (
            <div className="px-5 pb-3 flex flex-wrap gap-2 animate-fade-up delay-2">
              {crimeData && !crimeData.error && (
                <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${RISK_LEVEL_CONFIG[crimeData.risk_level]?.bg} ${RISK_LEVEL_CONFIG[crimeData.risk_level]?.text} ${RISK_LEVEL_CONFIG[crimeData.risk_level]?.border}`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${RISK_LEVEL_CONFIG[crimeData.risk_level]?.dot}`} />
                  Crime: {crimeData.risk_level}
                </div>
              )}
              {loadsheddingData && !loadsheddingData.error && (
                <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${RISK_LEVEL_CONFIG[loadsheddingData.risk_level]?.bg} ${RISK_LEVEL_CONFIG[loadsheddingData.risk_level]?.text} ${RISK_LEVEL_CONFIG[loadsheddingData.risk_level]?.border}`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${RISK_LEVEL_CONFIG[loadsheddingData.risk_level]?.dot}`} />
                  Load Shedding: {loadsheddingData.risk_level}
                </div>
              )}
              {municipalData && !municipalData.error && (() => {
                const level = getMuniHealthLevel(municipalData.health_score);
                const colors = MUNI_HEALTH_COLORS[level];
                return (
                  <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${colors.bg} ${colors.text} border-current/20`}>
                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: colors.hex }} />
                    Municipal: {colors.label}
                  </div>
                );
              })()}
            </div>
          )}

          {/* Biodiversity quick view */}
          {property.biodiversity?.length > 0 && (
            <Section title="Biodiversity Overlays" icon={Leaf} defaultOpen>
              <div className="space-y-2">
                {property.biodiversity.map((b, i) => {
                  const c = CBA_COLORS[b.cba_category];
                  return (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: c?.fill || '#9ca3af' }} />
                        <span className="text-gray-700 dark:text-gray-300">{c?.label || b.cba_category}</span>
                      </div>
                      <span className="text-gray-500">
                        {b.overlap_pct ? `${Math.round(b.overlap_pct)}%` : ''}
                      </span>
                    </div>
                  );
                })}
              </div>
              {property.biodiversity[0]?.vegetation_type && (
                <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                  Ecosystem: {property.biodiversity[0].vegetation_type}
                  {property.biodiversity[0].threat_status && (
                    <span className="ml-1 font-medium">
                      ({property.biodiversity[0].threat_status})
                    </span>
                  )}
                </div>
              )}
            </Section>
          )}

          {/* Heritage */}
          {property.heritage?.length > 0 && (
            <Section title={`Heritage (${property.heritage.length} record${property.heritage.length > 1 ? 's' : ''})`} icon={Shield}>
              <div className="space-y-2">
                {property.heritage.map((h, i) => (
                  <HeritageCard key={i} h={h} />
                ))}
              </div>
              <p className="text-[10px] text-gray-400 mt-2">
                Heritage inventory records indicate the property falls within a surveyed heritage area.
                Grade III sites may not be demolished or substantially altered without a heritage permit from Heritage Western Cape.
              </p>
            </Section>
          )}

          {/* Development Potential */}
          <Section title="Development Potential" icon={Ruler} defaultOpen>
            {devPotential === null ? (
              <div className="space-y-2"><div className="skeleton h-4 w-3/4" /><div className="skeleton h-4 w-1/2" /></div>
            ) : devPotential.error ? (
              <p className="text-xs text-gray-500">Development potential data unavailable</p>
            ) : (
              <div className="space-y-3 animate-fade-up">
                {/* Feasibility badge + zone code */}
                <div className="flex items-center gap-2">
                  <span className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
                    devPotential.feasibility === 'Feasible' ? 'bg-green-500/10 border-green-500/30 text-green-400' :
                    devPotential.feasibility === 'Not Feasible' ? 'bg-red-500/10 border-red-500/30 text-red-400' :
                    'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                  }`}>
                    {devPotential.feasibility}
                  </span>
                  {devPotential.zoning?.code && (
                    <span className="text-[11px] text-gray-500">{devPotential.zoning.code}</span>
                  )}
                  {devPotential.yield?.development_type && (
                    <span className="text-[10px] text-gray-500 capitalize">{devPotential.yield.development_type.replace(/_/g, ' ')}</span>
                  )}
                </div>

                {/* Key metrics grid */}
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2">
                    <div className="text-gray-400 text-[10px]">Max GFA</div>
                    <div className="font-semibold text-gray-900 dark:text-gray-100">
                      {devPotential.yield?.max_gfa_sqm ? `${Math.round(devPotential.yield.max_gfa_sqm).toLocaleString()} m²` : '\u2014'}
                    </div>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2">
                    <div className="text-gray-400 text-[10px]">Units</div>
                    <div className="font-semibold text-gray-900 dark:text-gray-100">
                      {devPotential.yield?.estimated_units || '\u2014'}
                    </div>
                  </div>
                  <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2">
                    <div className="text-gray-400 text-[10px]">Floors</div>
                    <div className="font-semibold text-gray-900 dark:text-gray-100">
                      {devPotential.yield?.effective_floors || '\u2014'}
                    </div>
                  </div>
                </div>

                {/* Unit Mix Breakdown */}
                {devPotential.unit_mix?.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Unit Mix</div>
                    {/* Stacked bar */}
                    <div className="h-3 bg-gray-700 rounded-full overflow-hidden flex">
                      {devPotential.unit_mix.filter(u => u.count > 0).map((u, i) => {
                        const colors = ['#a78bfa', '#818cf8', '#6366f1', '#4f46e5', '#3730a3', '#22c55e', '#f59e0b'];
                        const totalUnits = devPotential.yield?.estimated_units || 1;
                        return (
                          <div
                            key={i}
                            className="h-full"
                            title={`${u.label}: ${u.count} units`}
                            style={{ width: `${(u.count / totalUnits) * 100}%`, backgroundColor: colors[i % colors.length] }}
                          />
                        );
                      })}
                    </div>
                    {/* Unit list */}
                    <div className="space-y-0.5">
                      {devPotential.unit_mix.filter(u => u.count > 0).map((u, i) => {
                        const colors = ['#a78bfa', '#818cf8', '#6366f1', '#4f46e5', '#3730a3', '#22c55e', '#f59e0b'];
                        return (
                          <div key={i} className="flex items-center justify-between text-[11px]">
                            <div className="flex items-center gap-1.5">
                              <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: colors[i % colors.length] }} />
                              <span className="text-gray-400">{u.label}</span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="text-gray-500">{u.size_sqm} m²</span>
                              <span className="font-data text-gray-300 w-6 text-right">{u.count}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {devPotential.yield?.total_bedrooms > 0 && (
                      <div className="text-[10px] text-gray-500 pt-0.5">
                        {devPotential.yield.total_bedrooms} total bedrooms &middot; Avg {devPotential.yield.avg_unit_size_sqm} m²/unit
                      </div>
                    )}
                  </div>
                )}

                {/* Parking */}
                {devPotential.parking && (
                  <div className="space-y-1">
                    <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Parking</div>
                    <div className="grid grid-cols-3 gap-2 text-[11px]">
                      <div className="flex flex-col">
                        <span className="text-gray-500">Total</span>
                        <span className="font-data text-gray-300">{devPotential.parking.total_bays}</span>
                      </div>
                      <div className="flex flex-col">
                        <span className="text-gray-500">Resident</span>
                        <span className="font-data text-gray-300">{devPotential.parking.resident_bays}</span>
                      </div>
                      <div className="flex flex-col">
                        <span className="text-gray-500">Visitor</span>
                        <span className="font-data text-gray-300">{devPotential.parking.visitor_bays}</span>
                      </div>
                    </div>
                    <div className="text-[10px] text-gray-500 capitalize">
                      {devPotential.parking.recommended_solution} parking
                      {devPotential.parking.recommended_solution === 'basement' && ` (${devPotential.parking.basement_levels} level${devPotential.parking.basement_levels > 1 ? 's' : ''})`}
                    </div>
                  </div>
                )}

                {/* Financial Feasibility */}
                {devPotential.financials && (
                  <div className="space-y-1.5 pt-2 border-t border-gray-200 dark:border-gray-700">
                    <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wider flex items-center gap-1">
                      <DollarSign className="w-3 h-3" />
                      Financial Feasibility
                    </div>
                    <div className="space-y-0.5 text-[11px]">
                      <div className="flex justify-between">
                        <span className="text-gray-500">Construction</span>
                        <span className="font-data text-gray-300">R {(devPotential.financials.construction_cost / 1e6).toFixed(1)}M</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Prof. Fees + Contingency</span>
                        <span className="font-data text-gray-300">R {((devPotential.financials.professional_fees + devPotential.financials.contingency) / 1e6).toFixed(1)}M</span>
                      </div>
                      <div className="flex justify-between font-medium border-t border-gray-700 pt-0.5 mt-0.5">
                        <span className="text-gray-400">Total Dev Cost</span>
                        <span className="font-data text-gray-200">R {(devPotential.financials.total_development_cost / 1e6).toFixed(1)}M</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Est. Revenue</span>
                        <span className="font-data text-green-400">R {(devPotential.financials.estimated_revenue / 1e6).toFixed(1)}M</span>
                      </div>
                      <div className="flex justify-between font-medium">
                        <span className="text-gray-400">Est. Profit</span>
                        <span className={`font-data ${devPotential.financials.estimated_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          R {(devPotential.financials.estimated_profit / 1e6).toFixed(1)}M
                        </span>
                      </div>
                    </div>
                    {/* Margin bar */}
                    <div>
                      <div className="flex justify-between text-[11px] mb-0.5">
                        <span className="text-gray-400">Margin</span>
                        <span className={`font-data ${devPotential.financials.margin_pct >= 20 ? 'text-green-400' : devPotential.financials.margin_pct >= 15 ? 'text-yellow-400' : 'text-red-400'}`}>
                          {devPotential.financials.margin_pct}%
                        </span>
                      </div>
                      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(Math.max(devPotential.financials.margin_pct, 0), 100)}%`,
                            backgroundColor: devPotential.financials.margin_pct >= 20 ? '#22c55e' : devPotential.financials.margin_pct >= 15 ? '#eab308' : '#ef4444'
                          }}
                        />
                      </div>
                      <div className="text-[10px] text-gray-500 mt-0.5">
                        {devPotential.financials.viable ? 'Viable (margin >= 15%)' : 'Below viability threshold (< 15%)'}
                      </div>
                    </div>
                    <button
                      onClick={() => navigate(`/property/${propertyId}/financials`)}
                      className="w-full flex items-center justify-center gap-1.5 mt-2 py-1.5 rounded-lg
                                 text-[11px] font-medium text-ocean-400 hover:text-ocean-300
                                 bg-ocean-500/5 hover:bg-ocean-500/10 border border-ocean-500/20
                                 transition-all"
                    >
                      <ExternalLink className="w-3 h-3" />
                      View Financial Breakdown
                    </button>
                  </div>
                )}

                {/* Density Metrics */}
                {devPotential.density && (
                  <div className="space-y-1 pt-2 border-t border-gray-200 dark:border-gray-700">
                    <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Density</div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px]">
                      <div className="flex justify-between">
                        <span className="text-gray-500">Units/ha</span>
                        <span className="font-data text-gray-300">{devPotential.density.units_per_ha}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Beds/ha</span>
                        <span className="font-data text-gray-300">{devPotential.density.beds_per_ha}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">FAR Used</span>
                        <span className="font-data text-gray-300">{devPotential.density.far_utilization_pct}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Coverage Used</span>
                        <span className="font-data text-gray-300">{devPotential.density.coverage_utilization_pct}%</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Zoning rules summary */}
                {devPotential.zoning?.rules && (
                  <div className="text-[11px] text-gray-500 space-y-0.5 pt-2 border-t border-gray-200 dark:border-gray-700">
                    <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wider mb-1">Zoning Rules</div>
                    <div className="flex justify-between">
                      <span>FAR</span>
                      <span className="text-gray-300 font-data">{devPotential.zoning.rules.far}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Coverage</span>
                      <span className="text-gray-300 font-data">{devPotential.zoning.rules.coverage_pct}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Height Limit</span>
                      <span className="text-gray-300 font-data">{devPotential.zoning.rules.height_limit}m</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Setbacks (F/S/R)</span>
                      <span className="text-gray-300 font-data">{devPotential.zoning.rules.setback_front}/{devPotential.zoning.rules.setback_side}/{devPotential.zoning.rules.setback_rear}m</span>
                    </div>
                  </div>
                )}

                {/* Constraints */}
                {devPotential.constraints?.length > 0 && (
                  <div className="space-y-1 pt-2 border-t border-gray-200 dark:border-gray-700">
                    <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Constraints</div>
                    {devPotential.constraints.map((c, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <AlertTriangle className={`w-3 h-3 mt-0.5 shrink-0 ${c.severity === 'critical' ? 'text-red-400' : 'text-yellow-400'}`} />
                        <span className="text-gray-400">{c.message}</span>
                      </div>
                    ))}
                  </div>
                )}

                <p className="text-[10px] text-gray-400 leading-relaxed">
                  Screening-level estimate based on CTZS Table A. Actual development rights may vary.
                  {devPotential.zoning?.rules?.notes && <> {devPotential.zoning.rules.notes}</>}
                </p>
              </div>
            )}
          </Section>

          {/* Analysis button */}
          {!analysisRun && (
            <div className="px-4 py-4">
              <button
                onClick={runAnalysis}
                disabled={analysisLoading}
                className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-ocean-600 to-protea-600
                           text-white font-medium text-sm hover:from-ocean-700 hover:to-protea-700
                           disabled:opacity-50 disabled:cursor-not-allowed transition-all
                           flex items-center justify-center gap-2 shadow-sm"
              >
                {analysisLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Analysing...
                  </>
                ) : (
                  <>
                    <TrendingUp className="w-4 h-4" />
                    Calculate Potential
                  </>
                )}
              </button>
              <button
                onClick={showConstraintMap}
                className="w-full mt-2 py-2 px-4 rounded-xl border border-gray-300 dark:border-gray-600
                           text-gray-700 dark:text-gray-300 text-sm hover:bg-gray-50 dark:hover:bg-gray-800
                           transition-colors flex items-center justify-center gap-2"
              >
                <Ruler className="w-4 h-4" />
                Show Constraint Map
              </button>
              <button
                onClick={showSitePlan}
                disabled={sitePlanLoading}
                className="w-full mt-2 py-2 px-4 rounded-xl border border-ocean-400 dark:border-ocean-600
                           text-ocean-700 dark:text-ocean-300 text-sm hover:bg-ocean-50 dark:hover:bg-ocean-900/20
                           disabled:opacity-50 disabled:cursor-not-allowed
                           transition-colors flex items-center justify-center gap-2"
              >
                {sitePlanLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-ocean-500 border-t-transparent rounded-full animate-spin" />
                    Loading...
                  </>
                ) : (
                  <>
                    <Building className="w-4 h-4" />
                    Show Site Plan &amp; Massing
                  </>
                )}
              </button>
              <button
                onClick={() => setShowReport(true)}
                className="w-full mt-2 py-2 px-4 rounded-xl border border-protea-400 dark:border-protea-600
                           text-protea-700 dark:text-protea-300 text-sm hover:bg-protea-50 dark:hover:bg-protea-900/20
                           transition-colors flex items-center justify-center gap-2"
              >
                <Star className="w-4 h-4" />
                Generate Full Report
              </button>
              <button
                onClick={async () => {
                  setCapturingMap('sans');
                  const img = await captureMapImage(mapRef?.current).catch(() => null);
                  setMapImage(img);
                  setCapturingMap(null);
                  setShowSANSReport(true);
                }}
                disabled={capturingMap === 'sans'}
                className="w-full mt-2 py-2 px-4 rounded-xl border border-fynbos-400 dark:border-fynbos-600
                           text-fynbos-700 dark:text-fynbos-300 text-sm hover:bg-fynbos-50 dark:hover:bg-fynbos-900/20
                           transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {capturingMap === 'sans' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
                SANS 10400 Compliance Report
              </button>
              <button
                onClick={async () => {
                  setCapturingMap('site');
                  const img = await captureMapImage(mapRef?.current).catch(() => null);
                  setMapImage(img);
                  setCapturingMap(null);
                  setShowSiteAnalysis(true);
                }}
                disabled={capturingMap === 'site'}
                className="w-full mt-2 py-2 px-4 rounded-xl border border-ocean-400 dark:border-ocean-600
                           text-ocean-700 dark:text-ocean-300 text-sm hover:bg-ocean-50 dark:hover:bg-ocean-900/20
                           transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {capturingMap === 'site' ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
                Site Analysis Report
              </button>
            </div>
          )}

          {/* Property Comparison */}
          <Section title="Property Comparison" icon={DollarSign}>
            <div className="space-y-3">
              {/* Radius slider */}
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400 flex justify-between">
                  <span>Search Radius</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{radiusKm} km</span>
                </label>
                <input
                  type="range" min="0.5" max="5" step="0.5" value={radiusKm}
                  onChange={(e) => setRadiusKm(parseFloat(e.target.value))}
                  className="w-full h-1.5 mt-1 bg-gray-200 dark:bg-gray-700 rounded-full appearance-none cursor-pointer accent-ocean-600"
                />
                <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                  <span>0.5 km</span><span>5 km</span>
                </div>
              </div>

              <button
                onClick={runComparison}
                disabled={comparisonLoading}
                className="w-full py-2 px-4 rounded-xl bg-gradient-to-r from-fynbos-600 to-ocean-600
                           text-white font-medium text-sm hover:from-fynbos-700 hover:to-ocean-700
                           disabled:opacity-50 disabled:cursor-not-allowed transition-all
                           flex items-center justify-center gap-2 shadow-sm"
              >
                {comparisonLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Fetching valuations...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    Compare Properties
                  </>
                )}
              </button>

              {comparisonRun && radiusData && (
                <>
                  {/* Selected property value */}
                  {radiusData.selected_property?.market_value_zar && (
                    <div className="bg-ocean-50 dark:bg-ocean-900/20 rounded-lg p-2.5 border-l-3 border-ocean-500">
                      <div className="text-[10px] text-ocean-600 dark:text-ocean-400 uppercase tracking-wide mb-1">This Property</div>
                      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{fmtZar(radiusData.selected_property.market_value_zar)}</div>
                      <div className="text-xs text-gray-500">{radiusData.selected_property.value_per_sqm ? `R ${radiusData.selected_property.value_per_sqm.toLocaleString()}/m²` : ''}</div>
                    </div>
                  )}

                  {/* Radius results */}
                  {radiusData.count > 0 ? (
                    <>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {radiusData.count} valued properties within {radiusData.radius_km} km
                        {radiusData.total_in_radius ? ` (${radiusData.total_in_radius} total)` : ''}
                      </div>
                      <ComparisonCard label={`Cheapest in ${radiusData.radius_km} km`} data={radiusData.cheapest} color="border-green-500" />
                      <ComparisonCard label={`Most Expensive in ${radiusData.radius_km} km`} data={radiusData.most_expensive} color="border-red-500" />
                      {radiusData.stats && (
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2">
                            <div className="text-gray-400">Median Value</div>
                            <div className="font-semibold text-gray-900 dark:text-gray-100">{fmtZar(radiusData.stats.median_value)}</div>
                          </div>
                          <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2">
                            <div className="text-gray-400">Median /m²</div>
                            <div className="font-semibold text-gray-900 dark:text-gray-100">{radiusData.stats.median_per_sqm ? `R ${radiusData.stats.median_per_sqm.toLocaleString()}` : '\u2014'}</div>
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="text-xs text-gray-400 italic">No valued properties found in radius. Valuations are fetched on demand from the City of Cape Town — try a larger radius.</div>
                  )}
                </>
              )}

              {/* Suburb comparison */}
              {comparisonRun && suburbData && suburbData.count > 0 && (
                <>
                  <div className="border-t border-gray-200 dark:border-gray-700 pt-3 mt-2">
                    <div className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Suburb: {suburbData.suburb} ({suburbData.count} valued)
                    </div>
                    <ComparisonCard label="Cheapest in Suburb" data={suburbData.cheapest} color="border-green-500" />
                    <ComparisonCard label="Most Expensive in Suburb" data={suburbData.most_expensive} color="border-red-500" />
                    {suburbData.stats && (
                      <div className="grid grid-cols-2 gap-2 text-xs mt-2">
                        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2">
                          <div className="text-gray-400">Suburb Median</div>
                          <div className="font-semibold text-gray-900 dark:text-gray-100">{fmtZar(suburbData.stats.median_value)}</div>
                        </div>
                        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2">
                          <div className="text-gray-400">Suburb /m²</div>
                          <div className="font-semibold text-gray-900 dark:text-gray-100">{suburbData.stats.median_per_sqm ? `R ${suburbData.stats.median_per_sqm.toLocaleString()}` : '\u2014'}</div>
                        </div>
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* Construction cost */}
              {comparisonRun && constructionCost && constructionCost.cost_per_sqm && (
                <div className="border-t border-gray-200 dark:border-gray-700 pt-3 mt-2">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                    <Hammer className="w-3.5 h-3.5 text-amber-500" />
                    Construction Cost
                  </div>
                  <div className="bg-amber-50 dark:bg-amber-900/20 rounded-lg p-2.5">
                    <div className="text-xs text-gray-500 dark:text-gray-400">{constructionCost.label}</div>
                    <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mt-0.5">
                      R {constructionCost.cost_per_sqm.toLocaleString()}/m²
                    </div>
                    <div className="text-[10px] text-gray-400 mt-0.5">
                      Range: R {constructionCost.cost_range[0].toLocaleString()} – R {constructionCost.cost_range[1].toLocaleString()}/m²
                    </div>
                  </div>
                </div>
              )}

              <p className="text-[10px] text-gray-400 leading-relaxed">
                Property values from City of Cape Town GV2022 Municipal Valuation Roll (market value as at 1 July 2022).
                Construction costs based on AECOM Africa Cost Guide 2024/25.
              </p>
            </div>
          </Section>

          {/* Net Zero Scorecard */}
          {netzero && !netzero.error && (
            <>
              <Section title="Green Star Rating" icon={Star} defaultOpen>
                <div className="text-center py-2">
                  <div className={`text-3xl font-bold ${GREENSTAR_COLORS[netzero.greenstar_rating] || 'text-gray-400'}`}>
                    {netzero.greenstar_rating}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{netzero.greenstar_label}</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-gray-100 mt-1">
                    {netzero.total_score}/100
                  </div>
                </div>
                <GreenStarRadar data={[
                  { category: 'Energy', score: netzero.scores.energy, max: 35 },
                  { category: 'Water', score: netzero.scores.water, max: 25 },
                  { category: 'Ecology', score: netzero.scores.ecology, max: 20 },
                  { category: 'Location', score: netzero.scores.location, max: 10 },
                  { category: 'Materials', score: netzero.scores.materials_innovation, max: 10 },
                ]} />
                <div className="space-y-2.5 mt-3">
                  <ScoreBar label="Energy" score={netzero.scores.energy} max={35} color="bg-amber-500" help={SCORE_HELP.energy} />
                  <ScoreBar label="Water" score={netzero.scores.water} max={25} color="bg-blue-500" help={SCORE_HELP.water} />
                  <ScoreBar label="Ecology" score={netzero.scores.ecology} max={20} color="bg-green-500" help={SCORE_HELP.ecology} />
                  <ScoreBar label="Location" score={netzero.scores.location} max={10} color="bg-purple-500" help={SCORE_HELP.location} />
                  <ScoreBar label="Materials" score={netzero.scores.materials_innovation} max={10} color="bg-gray-500" help={SCORE_HELP.materials_innovation} />
                </div>
                <p className="text-[10px] text-gray-400 mt-3 leading-relaxed">
                  Based on GBCSA Green Star SA framework. Click the <Info className="w-2.5 h-2.5 inline" /> icons for category explanations.
                  Actual ratings require formal assessment by a registered Green Star AP.
                </p>
              </Section>

              <Section title="Solar Potential" icon={Sun}>
                <div className="space-y-1.5">
                  <InfoRow label="System Size" value={`${netzero.solar_summary.system_kwp} kWp`} />
                  <InfoRow label="Annual Generation" value={`${Math.round(netzero.solar_summary.annual_kwh).toLocaleString()} kWh`} />
                  <InfoRow label="Net Zero Ratio" value={`${Math.round(netzero.solar_summary.netzero_ratio * 100)}%`}
                           sub={netzero.solar_summary.netzero_ratio >= 1 ? 'Net Zero feasible' : 'Below target'} />
                  <InfoRow label="Carbon Offset" value={`${netzero.solar_summary.carbon_offset_tonnes} t CO\u2082/yr`} />
                </div>
                <p className="text-[10px] text-gray-400 mt-2">
                  Based on Cape Town avg 5.5 peak sun hours/day, 20% panel efficiency, 80% system performance ratio.
                  Net Zero ratio compares generation to SANS 10400-XA efficient building demand ({netzero.building_type}).
                </p>
              </Section>

              <Section title="Water Harvesting" icon={Droplets}>
                <div className="space-y-1.5">
                  <InfoRow label="Annual Harvest" value={`${netzero.water_summary.annual_harvest_kl} kl`} />
                  <InfoRow label="Demand Met" value={`${netzero.water_summary.demand_met_pct}%`} />
                  <InfoRow label="Recommended Tank" value={`${netzero.water_summary.recommended_tank_kl} kl`} />
                </div>
                <p className="text-[10px] text-gray-400 mt-2">
                  Rainfall zone affects harvest potential. Cape Town's winter rainfall pattern (May-Aug) means
                  summer months require stored water. Demand based on SANS 10252-1 ({netzero.building_type}).
                </p>
              </Section>

              {netzero.recommendations?.length > 0 && (
                <Section title="Recommendations" icon={AlertTriangle}>
                  <ul className="space-y-2">
                    {netzero.recommendations.map((r, i) => (
                      <li key={i} className="text-xs text-gray-600 dark:text-gray-400 flex gap-2">
                        <ChevronRight className="w-3 h-3 mt-0.5 text-fynbos-500 shrink-0" />
                        {r}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}
            </>
          )}

          {/* Biodiversity analysis results */}
          {biodiversity && !biodiversity.error && biodiversity.offset_applicable && (
            <Section title="Offset Requirement" icon={Leaf}>
              <div className="space-y-1.5">
                <InfoRow label="Designation" value={biodiversity.designation} />
                <InfoRow label="Base Ratio" value={`${biodiversity.base_ratio}:1`} />
                <InfoRow label="Required Offset" value={`${biodiversity.required_offset_ha} ha`} />
                {biodiversity.offset_cost_estimate_zar > 0 && (
                  <InfoRow label="Est. Cost" value={`R ${Math.round(biodiversity.offset_cost_estimate_zar).toLocaleString()}`} />
                )}
              </div>
            </Section>
          )}

          {/* Crime Risk */}
          <Section title="Crime Risk" icon={Siren} defaultOpen={false}>
            {crimeData === null ? (
              <div className="space-y-2"><div className="skeleton h-4 w-3/4" /><div className="skeleton h-4 w-1/2" /></div>
            ) : crimeData.error ? (
              <p className="text-xs text-gray-500">Crime data unavailable</p>
            ) : (
              <div className="space-y-3 animate-fade-up">
                {/* Score gauge */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-400">Crime Score</span>
                  <span className={`font-data text-lg font-bold ${RISK_LEVEL_CONFIG[crimeData.risk_level]?.text}`}>
                    {crimeData.crime_score}
                    <span className="text-xs text-gray-500 font-sans">/100</span>
                  </span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full animate-fill-bar"
                    style={{ width: `${crimeData.crime_score}%`, backgroundColor: RISK_LEVEL_CONFIG[crimeData.risk_level]?.hex }}
                  />
                </div>

                {/* Station info */}
                {crimeData.station && (
                  <div className="text-[11px] text-gray-500">
                    Station: <span className="text-gray-300">{crimeData.station.station_name}</span>
                    {crimeData.year && <> ({crimeData.year})</>}
                  </div>
                )}
                {crimeData.estimated && (
                  <div className="text-[11px] text-yellow-500/80 italic">{crimeData.note}</div>
                )}

                {/* Top categories chart */}
                {crimeData.top_categories?.length > 0 && (
                  <div className="mt-2">
                    <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wider mb-2">Top Categories</div>
                    <CrimeBarChart data={crimeData.top_categories} maxItems={6} />
                  </div>
                )}

                {/* Recommendations */}
                {crimeData.recommendations?.length > 0 && (
                  <div className="space-y-1 mt-2 pt-2 border-t border-gray-800">
                    <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Security Recommendations</div>
                    {crimeData.recommendations.map((rec, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <ChevronRight className="w-3 h-3 text-gray-600 mt-0.5 shrink-0" />
                        <div>
                          <span className="text-gray-300">{rec.action}</span>
                          <span className="text-gray-600 ml-1">{rec.cost_estimate_zar}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Section>

          {/* Load Shedding Impact */}
          <Section title="Load Shedding" icon={BatteryCharging} defaultOpen={false}>
            {loadsheddingData === null ? (
              <div className="space-y-2"><div className="skeleton h-4 w-3/4" /><div className="skeleton h-4 w-1/2" /></div>
            ) : loadsheddingData.error ? (
              <p className="text-xs text-gray-500">Load shedding data unavailable</p>
            ) : (
              <div className="space-y-3 animate-fade-up">
                {/* Baseline score */}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-400">Baseline Impact (Stage 4)</span>
                  <span className={`font-data text-lg font-bold ${RISK_LEVEL_CONFIG[loadsheddingData.risk_level]?.text}`}>
                    {loadsheddingData.baseline_impact_score}
                    <span className="text-xs text-gray-500 font-sans">/100</span>
                  </span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full animate-fill-bar"
                    style={{ width: `${loadsheddingData.baseline_impact_score}%`, backgroundColor: RISK_LEVEL_CONFIG[loadsheddingData.risk_level]?.hex }}
                  />
                </div>

                {/* Block info */}
                {loadsheddingData.block && (
                  <div className="text-[11px] text-gray-500">
                    Block: <span className="text-gray-300">{loadsheddingData.block.block_name || `Block ${loadsheddingData.block.block_number}`}</span>
                  </div>
                )}
                <div className="text-[11px] text-gray-500">
                  Property Type: <span className="text-gray-300 capitalize">{loadsheddingData.property_type}</span>
                </div>

                {/* Stage impacts chart */}
                <div className="mt-2">
                  <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wider mb-2">Stage Impacts (hrs/day)</div>
                  <StageImpactChart data={[1,2,3,4,5,6,7,8].map(stage => {
                    const impact = loadsheddingData.stage_impacts?.[`stage_${stage}`];
                    return { stage, hours_per_day: impact?.hours_per_day || 0 };
                  })} />
                  <div className="hidden">
                  </div>
                </div>

                {/* Recommendations */}
                {loadsheddingData.recommendations?.length > 0 && (
                  <div className="space-y-1 mt-2 pt-2 border-t border-gray-800">
                    <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Backup Power</div>
                    {loadsheddingData.recommendations.map((rec, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <ChevronRight className="w-3 h-3 text-gray-600 mt-0.5 shrink-0" />
                        <div>
                          <span className="text-gray-300">{rec.action}</span>
                          <span className="text-gray-600 ml-1">{rec.cost_estimate_zar}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Section>

          {/* Municipal Health */}
          <Section title="Municipal Health" icon={Landmark} defaultOpen={false}>
            {municipalData === null ? (
              <div className="space-y-2"><div className="skeleton h-4 w-3/4" /><div className="skeleton h-4 w-1/2" /></div>
            ) : municipalData.error ? (
              <p className="text-xs text-gray-500">Municipal data unavailable</p>
            ) : (
              <div className="space-y-3 animate-fade-up">
                {/* Health score gauge */}
                <HealthGauge score={municipalData.health_score} label="Infrastructure Health" />

                {/* Municipality info */}
                <div className="text-[11px] text-gray-500">
                  Municipality: <span className="text-gray-300">{municipalData.municipality}</span>
                  {municipalData.financial_year && <> ({municipalData.financial_year})</>}
                </div>

                {/* Financial indicators */}
                {municipalData.indicators && (
                  <div className="space-y-2 mt-2">
                    <div className="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Financial Indicators</div>
                    {Object.entries(municipalData.indicators).map(([key, val]) => (
                      <div key={key}>
                        <div className="flex justify-between text-xs mb-0.5">
                          <span className="text-gray-400 capitalize">{key.replace(/_/g, ' ')}</span>
                          <span className="font-data text-gray-300">{typeof val.score === 'number' ? val.score : val.value}</span>
                        </div>
                        {typeof val.score === 'number' && (
                          <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                            <div className="h-full rounded-full animate-fill-bar bg-ocean-500" style={{ width: `${Math.min(val.score, 100)}%` }} />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Trend */}
                {municipalData.trend && (
                  <div className="text-[11px] text-gray-500 mt-1 pt-2 border-t border-gray-800">
                    Trend: <span className={municipalData.trend === 'improving' ? 'text-green-400' : municipalData.trend === 'declining' ? 'text-red-400' : 'text-gray-400'}>
                      {municipalData.trend === 'improving' ? '\u2191 Improving' : municipalData.trend === 'declining' ? '\u2193 Declining' : '\u2192 Stable'}
                    </span>
                  </div>
                )}
              </div>
            )}
          </Section>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
          Property not found
        </div>
      )}

      {showReport && (
        <ReportView propertyId={propertyId} onClose={() => setShowReport(false)} />
      )}
      {showSANSReport && (
        <SANSComplianceReport
          propertyId={propertyId}
          mapImage={mapImage}
          propertyGeometry={property?.geometry}
          areaSqm={property?.area_sqm}
          onClose={() => { setShowSANSReport(false); setMapImage(null); }}
        />
      )}
      {showSiteAnalysis && (
        <SiteAnalysisReport
          propertyId={propertyId}
          mapImage={mapImage}
          propertyGeometry={property?.geometry}
          areaSqm={property?.area_sqm}
          onClose={() => { setShowSiteAnalysis(false); setMapImage(null); }}
        />
      )}
    </div>
  );
}
