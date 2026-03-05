import { useState, useEffect, useCallback, useRef } from 'react';
import {
  X, ChevronUp, ChevronDown, Building, MapPin, Ruler, DollarSign,
  Layers, Shield, Leaf, Siren, Eye, EyeOff, Activity,
  BatteryCharging, Grid3X3, AlertTriangle, Landmark,
  Building2, Crosshair, Box,
} from 'lucide-react';
import {
  getProperty, getDevelopmentPotential, getSitePlan, getMassing,
  getConstraintMap, getCrimeRisk, getLoadshedding, getMunicipalHealth,
  getBiodiversityAnalysis,
} from '../utils/api';
import { getMuniHealthLevel, MUNI_HEALTH_COLORS } from '../utils/constants';

// --- Formatting ---
const fmt = {
  area: (v) => v ? Math.round(v).toLocaleString() : '—',
  money: (v) => v ? `R ${(v / 1e6).toFixed(1)}M` : '—',
  pct: (v) => v != null ? `${v.toFixed(1)}%` : '—',
};

// --- Sub-components ---

function MetricCard({ label, value, sub, icon: Icon, status }) {
  const borderClass = status === 'good' ? 'border-green-500/30'
    : status === 'warning' ? 'border-yellow-500/30'
    : status === 'critical' ? 'border-red-500/30'
    : 'border-gray-800/50';

  return (
    <div className={`bg-gray-900/60 border ${borderClass} rounded-lg px-3 py-2.5 min-w-[110px] shrink-0 transition-all hover:bg-gray-800/60`}>
      <div className="flex items-center gap-1.5 mb-1">
        {Icon && <Icon className="w-3 h-3 text-gray-600" />}
        <span className="text-[9px] font-semibold text-gray-600 uppercase tracking-[0.15em] font-data">{label}</span>
      </div>
      <div className="text-base font-bold text-white font-data tracking-tight leading-tight">{value}</div>
      {sub && <div className="text-[10px] text-gray-500 font-data mt-0.5">{sub}</div>}
    </div>
  );
}

function RiskCard({ label, value, detail, level, icon: Icon, loading }) {
  const cfg = {
    Critical: { dot: 'bg-red-500', text: 'text-red-400', border: 'border-red-500/30', bg: 'bg-red-500/5' },
    High: { dot: 'bg-orange-500', text: 'text-orange-400', border: 'border-orange-500/30', bg: 'bg-orange-500/5' },
    Medium: { dot: 'bg-yellow-500', text: 'text-yellow-400', border: 'border-yellow-500/30', bg: 'bg-yellow-500/5' },
    Low: { dot: 'bg-green-500', text: 'text-green-400', border: 'border-green-500/30', bg: 'bg-green-500/5' },
    clear: { dot: 'bg-green-500', text: 'text-green-400', border: 'border-green-500/30', bg: 'bg-green-500/5' },
    'no-go': { dot: 'bg-red-500', text: 'text-red-400', border: 'border-red-500/30', bg: 'bg-red-500/5' },
    offset: { dot: 'bg-amber-500', text: 'text-amber-400', border: 'border-amber-500/30', bg: 'bg-amber-500/5' },
    exceptional: { dot: 'bg-orange-500', text: 'text-orange-400', border: 'border-orange-500/30', bg: 'bg-orange-500/5' },
    good: { dot: 'bg-green-500', text: 'text-green-400', border: 'border-green-500/30', bg: 'bg-green-500/5' },
    fair: { dot: 'bg-yellow-500', text: 'text-yellow-400', border: 'border-yellow-500/30', bg: 'bg-yellow-500/5' },
    poor: { dot: 'bg-orange-500', text: 'text-orange-400', border: 'border-orange-500/30', bg: 'bg-orange-500/5' },
    critical: { dot: 'bg-red-500', text: 'text-red-400', border: 'border-red-500/30', bg: 'bg-red-500/5' },
  }[level] || { dot: 'bg-gray-500', text: 'text-gray-400', border: 'border-gray-800/50', bg: '' };

  if (loading) {
    return (
      <div className="bg-gray-900/60 border border-gray-800/50 rounded-lg px-3 py-2.5 min-w-[130px] shrink-0">
        <div className="flex items-center gap-1.5 mb-2">
          {Icon && <Icon className="w-3 h-3 text-gray-600" />}
          <span className="text-[9px] font-semibold text-gray-600 uppercase tracking-[0.15em] font-data">{label}</span>
        </div>
        <div className="skeleton h-4 w-16 mb-1" />
        <div className="skeleton h-3 w-20" />
      </div>
    );
  }

  return (
    <div className={`${cfg.bg} border ${cfg.border} rounded-lg px-3 py-2.5 min-w-[130px] shrink-0 transition-all`}>
      <div className="flex items-center gap-1.5 mb-1.5">
        {Icon && <Icon className={`w-3 h-3 ${cfg.text}`} />}
        <span className="text-[9px] font-semibold text-gray-600 uppercase tracking-[0.15em] font-data">{label}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className={`w-2 h-2 rounded-full ${cfg.dot}`} />
        <span className={`text-sm font-bold font-data ${cfg.text}`}>{value}</span>
      </div>
      {detail && <div className="text-[10px] text-gray-500 mt-0.5">{detail}</div>}
    </div>
  );
}

function OverlayButton({ label, active, onClick, loading, icon: Icon }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-semibold uppercase tracking-wider font-data transition-all
        ${active
          ? 'bg-ocean-500/15 text-ocean-400 border border-ocean-500/30'
          : 'bg-gray-900/50 text-gray-500 border border-gray-800/40 hover:border-gray-700/50 hover:text-gray-300'
        } ${loading ? 'opacity-50' : ''}`}
    >
      {loading ? (
        <div className="w-3 h-3 border border-ocean-400 border-t-transparent rounded-full animate-spin" />
      ) : active ? (
        <Eye className="w-3 h-3" />
      ) : (
        <EyeOff className="w-3 h-3" />
      )}
      {Icon && <Icon className="w-3 h-3" />}
      {label}
    </button>
  );
}

function SkeletonRow() {
  return (
    <div className="flex gap-2.5 overflow-x-auto pb-1">
      {[1, 2, 3, 4, 5].map(i => (
        <div key={i} className="bg-gray-900/60 border border-gray-800/50 rounded-lg px-3 py-2.5 min-w-[110px] shrink-0">
          <div className="skeleton h-3 w-12 mb-2" />
          <div className="skeleton h-5 w-16" />
        </div>
      ))}
    </div>
  );
}

// --- Mode tabs ---
const MODES = [
  { id: 'overview', label: 'INTEL', icon: Activity },
  { id: 'develop', label: 'DEVELOP', icon: Building },
  { id: 'risk', label: 'RISK', icon: Shield },
];

// --- Mode content components ---

function OverviewContent({ property }) {
  if (!property) return <SkeletonRow />;
  const p = property;

  return (
    <div className="flex gap-2.5 overflow-x-auto pb-1 hud-scroll">
      <MetricCard label="AREA" value={`${fmt.area(p.area_sqm)} m²`} icon={Ruler} />
      <MetricCard label="ZONING" value={p.zoning || '—'} icon={Grid3X3} />
      <MetricCard
        label="VALUE"
        value={fmt.money(p.market_value_zar)}
        sub={p.area_sqm && p.market_value_zar ? `R ${Math.round(p.market_value_zar / p.area_sqm).toLocaleString()}/m²` : null}
        icon={DollarSign}
      />
      <MetricCard label="LAND USE" value={p.land_use_category || '—'} icon={Building} />
      <MetricCard label="SUBURB" value={p.suburb || '—'} icon={MapPin} />
      {p.heritage_sites?.length > 0 && (
        <MetricCard
          label="HERITAGE"
          value={`${p.heritage_sites.length}`}
          sub={`site${p.heritage_sites.length > 1 ? 's' : ''}`}
          icon={Landmark}
          status="warning"
        />
      )}
    </div>
  );
}

function DevelopContent({ data, loading, activeOverlay, constraintActive, onToggleOverlay }) {
  if (loading) {
    return (
      <div className="flex gap-2.5 overflow-x-auto pb-1 hud-scroll">
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div key={i} className="bg-gray-900/60 border border-gray-800/50 rounded-lg px-3 py-2.5 min-w-[110px] shrink-0">
            <div className="skeleton h-3 w-12 mb-2" />
            <div className="skeleton h-5 w-8" />
          </div>
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-4">
        <div className="text-xs text-gray-500">No development data available for this property.</div>
      </div>
    );
  }

  const d = data;
  const fin = d.financials;
  const marginColor = fin?.margin_pct >= 20 ? 'text-green-400' : fin?.margin_pct >= 15 ? 'text-yellow-400' : 'text-red-400';
  const profitColor = fin?.estimated_profit >= 0 ? 'text-green-400' : 'text-red-400';
  const totalUnits = d.yield?.estimated_units || d.unit_mix?.reduce((s, u) => s + u.count, 0) || 0;

  return (
    <div className="space-y-3">
      {/* Key metrics */}
      <div className="flex gap-2.5 overflow-x-auto pb-1 hud-scroll">
        <MetricCard label="UNITS" value={totalUnits || '—'} icon={Building} />
        <MetricCard label="GFA" value={d.yield?.gfa_sqm ? `${fmt.area(d.yield.gfa_sqm)}` : '—'} sub="m²" icon={Ruler} />
        <MetricCard label="HEIGHT" value={d.zoning?.rules ? `${d.zoning.rules.max_floors}F` : '—'} sub={d.zoning?.rules ? `${d.zoning.rules.height_limit}m` : null} icon={Building2} />
        <MetricCard label="PARKING" value={d.parking?.total_bays || '—'} sub="bays" icon={Grid3X3} />
        <MetricCard label="FAR" value={d.zoning?.rules?.far ?? '—'} icon={Layers} />
        <MetricCard label="COVERAGE" value={d.zoning?.rules ? `${d.zoning.rules.coverage_pct}%` : '—'} icon={Box} />
      </div>

      {/* Financials + Overlay controls */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        {fin && (
          <div className="flex items-center gap-3 text-[11px] font-data flex-wrap">
            <span><span className="text-gray-600 mr-1">COST</span><span className="text-gray-300">{fmt.money(fin.total_development_cost)}</span></span>
            <span><span className="text-gray-600 mr-1">REV</span><span className="text-green-400">{fmt.money(fin.estimated_revenue)}</span></span>
            <span><span className="text-gray-600 mr-1">PROFIT</span><span className={profitColor}>{fmt.money(fin.estimated_profit)}</span></span>
            <span><span className="text-gray-600 mr-1">MARGIN</span><span className={marginColor}>{fmt.pct(fin.margin_pct)}</span></span>
          </div>
        )}

        <div className="flex items-center gap-1.5 shrink-0">
          <OverlayButton label="SITE PLAN" active={activeOverlay === 'sitePlan'} onClick={() => onToggleOverlay('sitePlan')} icon={Crosshair} />
          <OverlayButton label="MASSING" active={activeOverlay === 'massing'} onClick={() => onToggleOverlay('massing')} icon={Box} />
          <div className="w-px h-5 bg-gray-800 mx-0.5" />
          <OverlayButton label="CONSTRAINTS" active={constraintActive} onClick={() => onToggleOverlay('constraints')} icon={AlertTriangle} />
        </div>
      </div>

      {/* Unit mix bar */}
      {d.unit_mix?.length > 0 && totalUnits > 0 && (
        <div className="flex items-center gap-3">
          <span className="text-[9px] font-semibold text-gray-600 uppercase tracking-[0.15em] font-data shrink-0">MIX</span>
          <div className="h-2.5 bg-gray-800 rounded-full overflow-hidden flex flex-1">
            {d.unit_mix.filter(u => u.count > 0).map((u, i) => {
              const colors = ['#a78bfa', '#818cf8', '#6366f1', '#4f46e5', '#22c55e', '#f59e0b', '#ef4444'];
              return (
                <div
                  key={i}
                  className="h-full transition-all"
                  title={`${u.label}: ${u.count} units`}
                  style={{ width: `${(u.count / totalUnits) * 100}%`, backgroundColor: colors[i % colors.length] }}
                />
              );
            })}
          </div>
          <div className="flex items-center gap-2 text-[10px] text-gray-500 font-data shrink-0">
            {d.unit_mix.filter(u => u.count > 0).slice(0, 4).map((u, i) => {
              const colors = ['#a78bfa', '#818cf8', '#6366f1', '#4f46e5', '#22c55e', '#f59e0b', '#ef4444'];
              return (
                <span key={i} className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: colors[i % colors.length] }} />
                  {u.label} {u.count}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function RiskContent({ bio, crime, loadshedding, municipal, loading }) {
  // Derive bio status from analysis response
  const bioLevel = bio
    ? bio.is_no_go ? 'no-go'
      : bio.designation && ['CBA 1b', 'CBA 1c'].includes(bio.designation) ? 'exceptional'
      : bio.offset_applicable ? 'offset'
      : 'clear'
    : null;
  const bioLabels = { clear: 'Clear', 'no-go': 'No-Go', offset: 'Offset', exceptional: 'Exceptional' };

  const muniScore = municipal?.overall_score;
  const muniLevel = muniScore != null ? getMuniHealthLevel(muniScore) : null;

  return (
    <div className="flex gap-2.5 overflow-x-auto pb-1 hud-scroll">
      <RiskCard
        label="BIODIVERSITY"
        value={bioLabels[bioLevel] || '—'}
        detail={bio?.designation || 'No CBA overlay'}
        level={bioLevel}
        icon={Leaf}
        loading={loading.bio}
      />
      <RiskCard
        label="CRIME"
        value={crime?.risk_level || '—'}
        detail={crime?.risk_score != null ? `Score: ${crime.risk_score.toFixed(1)}` : null}
        level={crime?.risk_level}
        icon={Siren}
        loading={loading.crime}
      />
      <RiskCard
        label="LOAD SHEDDING"
        value={loadshedding?.risk_level || '—'}
        detail={loadshedding?.block ? `Block ${loadshedding.block.block_number ?? loadshedding.block}` : null}
        level={loadshedding?.risk_level}
        icon={BatteryCharging}
        loading={loading.loadshedding}
      />
      <RiskCard
        label="MUNICIPAL"
        value={muniScore != null ? `${muniScore}` : '—'}
        detail={muniLevel ? MUNI_HEALTH_COLORS[muniLevel]?.label : null}
        level={muniLevel}
        icon={Landmark}
        loading={loading.municipal}
      />
    </div>
  );
}

// --- Main Component ---

export default function CommandHUD({
  propertyId,
  onClose,
  onShowSitePlan,
  onShowConstraintMap,
}) {
  const [property, setProperty] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [activeMode, setActiveMode] = useState('overview');

  // Analysis data
  const [devPotential, setDevPotential] = useState(null);
  const [crimeData, setCrimeData] = useState(null);
  const [loadsheddingData, setLoadsheddingData] = useState(null);
  const [municipalData, setMunicipalData] = useState(null);
  const [bioData, setBioData] = useState(null);

  // Overlays
  const [activeOverlay, setActiveOverlay] = useState(null); // 'sitePlan' | 'massing'
  const [constraintActive, setConstraintActive] = useState(false);

  // Loading
  const [loadingState, setLoadingState] = useState({});
  const setLoading = useCallback((key, val) => setLoadingState(prev => ({ ...prev, [key]: val })), []);

  // Fetch tracking refs
  const devFetched = useRef(false);
  const riskFetched = useRef(false);

  // Reset on property change
  useEffect(() => {
    if (!propertyId) return;
    setProperty(null);
    setDevPotential(null);
    setCrimeData(null);
    setLoadsheddingData(null);
    setMunicipalData(null);
    setBioData(null);
    setActiveOverlay(null);
    setConstraintActive(false);
    setActiveMode('overview');
    setExpanded(true);
    setLoadingState({});
    devFetched.current = false;
    riskFetched.current = false;

    setLoading('property', true);
    getProperty(propertyId)
      .then(setProperty)
      .catch(console.error)
      .finally(() => setLoading('property', false));
  }, [propertyId, setLoading]);

  // Lazy fetch: development potential
  useEffect(() => {
    if (activeMode !== 'develop' || !propertyId || devFetched.current) return;
    devFetched.current = true;
    setLoading('develop', true);
    getDevelopmentPotential(propertyId)
      .then(setDevPotential)
      .catch(console.error)
      .finally(() => setLoading('develop', false));
  }, [activeMode, propertyId, setLoading]);

  // Lazy fetch: risk data (all 4 in parallel)
  useEffect(() => {
    if (activeMode !== 'risk' || !propertyId || riskFetched.current) return;
    riskFetched.current = true;

    setLoadingState(prev => ({ ...prev, bio: true, crime: true, loadshedding: true, municipal: true }));

    getBiodiversityAnalysis(propertyId, 500)
      .then(setBioData).catch(() => {}).finally(() => setLoading('bio', false));
    getCrimeRisk(propertyId)
      .then(setCrimeData).catch(() => {}).finally(() => setLoading('crime', false));
    getLoadshedding(propertyId)
      .then(setLoadsheddingData).catch(() => {}).finally(() => setLoading('loadshedding', false));
    getMunicipalHealth(propertyId)
      .then(setMunicipalData).catch(() => {}).finally(() => setLoading('municipal', false));
  }, [activeMode, propertyId, setLoading]);

  // Overlay toggles
  const handleToggleOverlay = useCallback(async (type) => {
    if (type === 'constraints') {
      const next = !constraintActive;
      setConstraintActive(next);
      if (next) {
        try {
          const data = await getConstraintMap(propertyId);
          onShowConstraintMap?.(data);
        } catch { onShowConstraintMap?.(null); setConstraintActive(false); }
      } else {
        onShowConstraintMap?.(null);
      }
    } else {
      // sitePlan / massing are mutually exclusive
      const next = activeOverlay === type ? null : type;
      setActiveOverlay(next);
      if (next) {
        try {
          const data = type === 'sitePlan'
            ? await getSitePlan(propertyId)
            : await getMassing(propertyId);
          onShowSitePlan?.(data);
        } catch { onShowSitePlan?.(null); setActiveOverlay(null); }
      } else {
        onShowSitePlan?.(null);
      }
    }
  }, [propertyId, activeOverlay, constraintActive, onShowSitePlan, onShowConstraintMap]);

  // --- Idle state ---
  if (!propertyId) {
    return (
      <div className="shrink-0">
        <div className="h-px bg-gradient-to-r from-transparent via-ocean-500/15 to-transparent" />
        <div className="bg-gray-950/70 backdrop-blur-md">
          <div className="flex items-center justify-center gap-3 h-9 px-4">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500/80 animate-pulse" />
            <span className="text-[10px] font-data text-gray-600 uppercase tracking-[0.15em]">SITELINE</span>
            <span className="text-gray-800 font-data text-[10px]">|</span>
            <span className="text-[10px] font-data text-gray-600">Search a property to begin analysis</span>
          </div>
        </div>
      </div>
    );
  }

  // --- Active state ---
  const p = property;

  return (
    <div className="h-full flex flex-col">
      {/* Glow line */}
      <div className="h-px bg-gradient-to-r from-transparent via-ocean-500/40 to-transparent shrink-0" />

      <div className="hud-bg backdrop-blur-xl border-t border-gray-800/30 relative hud-scanlines flex-1 flex flex-col min-h-0">
          {/* Compact title bar */}
          <div className="flex items-center gap-3 px-4 h-11 relative z-10">
            {/* Status indicator */}
            <div className="flex items-center gap-1.5 shrink-0">
              <div className="w-2 h-2 rounded-full bg-ocean-400 animate-pulse-risk" />
              <span className="text-[9px] font-semibold text-ocean-400/80 uppercase tracking-[0.2em] font-data">
                ACTIVE
              </span>
            </div>

            {/* Property info */}
            <div className="flex items-center gap-2 min-w-0 flex-1">
              {loadingState.property ? (
                <div className="skeleton h-4 w-48" />
              ) : p ? (
                <>
                  <span className="text-sm font-bold text-white truncate">ERF {p.erf_number}</span>
                  <span className="text-[10px] text-gray-600 font-data hidden sm:inline">/</span>
                  <span className="text-xs text-gray-500 truncate hidden sm:inline">{p.suburb}</span>
                  {p.zoning && (
                    <span className="text-[10px] font-data text-ocean-400 bg-ocean-500/10 px-1.5 py-0.5 rounded border border-ocean-500/20 shrink-0">
                      {p.zoning}
                    </span>
                  )}
                </>
              ) : null}
            </div>

            {/* Quick stats */}
            {p && (
              <div className="items-center gap-4 shrink-0 hidden md:flex text-[11px] font-data">
                <span className="text-gray-400">
                  {p.area_sqm ? `${Math.round(p.area_sqm).toLocaleString()} m²` : ''}
                </span>
                {p.market_value_zar && (
                  <span className="text-gray-400">R {(p.market_value_zar / 1e6).toFixed(1)}M</span>
                )}
              </div>
            )}

            {/* Mode selector */}
            <div className="flex items-center gap-0.5 shrink-0 border-l border-gray-800/60 pl-3 ml-1">
              {MODES.map(mode => {
                const Icon = mode.icon;
                const isActive = activeMode === mode.id && expanded;
                return (
                  <button
                    key={mode.id}
                    onClick={() => {
                      if (activeMode === mode.id && expanded) {
                        setExpanded(false);
                      } else {
                        setActiveMode(mode.id);
                        setExpanded(true);
                      }
                    }}
                    className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-semibold uppercase tracking-wider font-data transition-all
                      ${isActive
                        ? 'text-ocean-400 bg-ocean-500/10 border border-ocean-500/20'
                        : 'text-gray-500 hover:text-gray-300 border border-transparent'
                      }`}
                  >
                    <Icon className="w-3 h-3" />
                    <span className="hidden lg:inline">{mode.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1 shrink-0 border-l border-gray-800/60 pl-2 ml-1">
              <button
                onClick={() => setExpanded(!expanded)}
                className="w-7 h-7 rounded-md flex items-center justify-center text-gray-500 hover:text-gray-300
                          hover:bg-gray-800/50 transition-colors"
              >
                {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
              </button>
              <button
                onClick={onClose}
                className="w-7 h-7 rounded-md flex items-center justify-center text-gray-600 hover:text-red-400
                          hover:bg-red-500/10 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Expanded panel */}
          <div
            className={`overflow-hidden transition-all duration-300 ease-in-out relative z-10
              ${expanded ? 'flex-1 opacity-100 min-h-0' : 'h-0 opacity-0'}`}
          >
            <div className="border-t border-gray-800/30 px-4 py-3 h-full overflow-y-auto sidebar-scroll">
              {activeMode === 'overview' && <OverviewContent property={p} />}
              {activeMode === 'develop' && (
                <DevelopContent
                  data={devPotential}
                  loading={loadingState.develop}
                  activeOverlay={activeOverlay}
                  constraintActive={constraintActive}
                  onToggleOverlay={handleToggleOverlay}
                />
              )}
              {activeMode === 'risk' && (
                <RiskContent
                  bio={bioData}
                  crime={crimeData}
                  loadshedding={loadsheddingData}
                  municipal={municipalData}
                  loading={loadingState}
                />
              )}
            </div>
          </div>
        </div>
      </div>
  );
}
