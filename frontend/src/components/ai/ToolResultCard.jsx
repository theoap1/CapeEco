import { Search, MapPin, Shield, Zap, BarChart3, Map, AlertTriangle, Battery, Building2, TrendingUp, TrendingDown, Minus, Ruler, CheckCircle, XCircle, Info } from 'lucide-react';
import { GreenStarRadar, CrimeBarChart, StageImpactChart, HealthGauge } from '../AnalysisCharts';
import { CBA_COLORS, RISK_LEVEL_CONFIG, GREENSTAR_COLORS } from '../../utils/constants';

const fmt = (v) => v != null ? Number(v).toLocaleString('en-ZA') : '—';
const fmtZar = (v) => v != null ? `R ${Number(v).toLocaleString('en-ZA', { minimumFractionDigits: 0 })}` : '—';

function CardWrapper({ icon: Icon, title, children }) {
  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-3 my-2 animate-fade-up">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-3.5 h-3.5 text-ocean-400" />
        <span className="text-xs font-semibold text-gray-300">{title}</span>
      </div>
      {children}
    </div>
  );
}

function StatBox({ label, value, sub }) {
  return (
    <div className="bg-gray-900/50 rounded-lg p-2">
      <div className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</div>
      <div className="text-sm font-semibold text-white font-data">{value}</div>
      {sub && <div className="text-[10px] text-gray-500">{sub}</div>}
    </div>
  );
}

function GaugeBar({ value, max = 100, color }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="gauge-track">
      <div className="gauge-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

// --- Search Results ---
function SearchResultCard({ data }) {
  const results = data.results || [];
  if (!results.length) return null;
  return (
    <CardWrapper icon={Search} title={`${results.length} propert${results.length === 1 ? 'y' : 'ies'} found (${data.match_type || 'search'})`}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-1 px-1.5 text-gray-500 font-medium text-[10px] uppercase tracking-wider">ERF</th>
              <th className="text-left py-1 px-1.5 text-gray-500 font-medium text-[10px] uppercase tracking-wider">Suburb</th>
              <th className="text-right py-1 px-1.5 text-gray-500 font-medium text-[10px] uppercase tracking-wider">Area</th>
              <th className="text-left py-1 px-1.5 text-gray-500 font-medium text-[10px] uppercase tracking-wider">Zoning</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r, i) => (
              <tr key={i} className="border-b border-gray-800/50">
                <td className="py-1 px-1.5 text-white font-data">{r.erf_number}</td>
                <td className="py-1 px-1.5 text-gray-300">{r.suburb}</td>
                <td className="py-1 px-1.5 text-gray-300 text-right font-data">{r.area_sqm ? `${fmt(Math.round(r.area_sqm))} m²` : '—'}</td>
                <td className="py-1 px-1.5 text-gray-400">{r.zoning_primary || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </CardWrapper>
  );
}

// --- Property Details ---
function PropertyDetailsCard({ data }) {
  const address = data.full_address || `ERF ${data.erf_number}`;
  const biodiversity = data.biodiversity || [];
  const heritage = data.heritage || [];
  return (
    <CardWrapper icon={MapPin} title={address}>
      <div className="grid grid-cols-2 gap-1.5 mb-2">
        <StatBox label="Area" value={data.area_sqm ? `${fmt(Math.round(data.area_sqm))} m²` : '—'} />
        <StatBox label="Zoning" value={data.zoning_primary || '—'} />
        <StatBox label="Suburb" value={data.suburb || '—'} />
        <StatBox label="Urban Edge" value={data.inside_urban_edge ? 'Inside' : data.inside_urban_edge === false ? 'Outside' : '—'} />
      </div>
      {biodiversity.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {biodiversity.map((b, i) => {
            const color = CBA_COLORS[b.cba_category];
            return (
              <span key={i} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-900/80">
                <span className="w-2 h-2 rounded-full" style={{ background: color?.fill || '#6b7280' }} />
                <span className="text-gray-300">{b.cba_category}</span>
                {b.overlap_pct != null && <span className="text-gray-500">{Math.round(b.overlap_pct)}%</span>}
              </span>
            );
          })}
        </div>
      )}
      {heritage.length > 0 && (
        <div className="mt-2 text-[10px] text-gray-500">
          <Building2 className="w-3 h-3 inline mr-1" />
          {heritage.length} heritage record{heritage.length !== 1 ? 's' : ''} nearby
        </div>
      )}
    </CardWrapper>
  );
}

// --- Biodiversity ---
function BiodiversityCard({ data }) {
  const isNoGo = data.no_go || data.is_no_go;
  const designation = data.highest_cba || data.cba_category || data.designation;
  const ratio = data.offset_ratio || data.ratio;
  const cost = data.estimated_cost || data.cost_estimate;
  const requiredHa = data.required_hectares || data.required_ha;
  const riskColor = isNoGo ? '#ef4444' : ratio > 5 ? '#f97316' : ratio > 0 ? '#eab308' : '#22c55e';

  return (
    <CardWrapper icon={Shield} title="Biodiversity Offset Analysis">
      {isNoGo ? (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-2.5 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <div>
            <div className="text-sm font-semibold text-red-400">No-Go Zone</div>
            <div className="text-[11px] text-red-300/80">{designation} — development not permitted</div>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-1.5">
            {designation && <StatBox label="Designation" value={designation} />}
            {ratio != null && <StatBox label="Offset Ratio" value={`${ratio}:1`} />}
            {requiredHa != null && <StatBox label="Required Area" value={`${Number(requiredHa).toFixed(2)} ha`} />}
            {cost != null && <StatBox label="Est. Cost" value={fmtZar(cost)} />}
          </div>
          {ratio != null && (
            <div className="space-y-1">
              <div className="flex justify-between text-[10px]">
                <span className="text-gray-500">Offset severity</span>
                <span className="font-data" style={{ color: riskColor }}>{ratio}:1</span>
              </div>
              <GaugeBar value={Math.min(ratio, 30)} max={30} color={riskColor} />
            </div>
          )}
        </div>
      )}
    </CardWrapper>
  );
}

// --- Net Zero ---
function NetZeroCard({ data }) {
  const scorecard = data.scorecard;
  const solar = data.solar;
  const water = data.water;
  if (!scorecard && !solar && !water) return null;

  const rating = scorecard?.greenstar_rating || scorecard?.rating;
  const totalScore = scorecard?.total_score || scorecard?.score;
  const ratingColor = GREENSTAR_COLORS[rating] || 'text-gray-400';
  const scores = scorecard?.scores || scorecard?.category_scores || {};

  const radarData = scores ? [
    { category: 'Energy', score: scores.energy || 0, max: 35 },
    { category: 'Water', score: scores.water || 0, max: 25 },
    { category: 'Ecology', score: scores.ecology || 0, max: 20 },
    { category: 'Location', score: scores.location || 0, max: 10 },
    { category: 'Materials', score: scores.materials_innovation || scores.materials || 0, max: 10 },
  ] : null;

  return (
    <CardWrapper icon={Zap} title="Net Zero Scorecard">
      {rating && (
        <div className="flex items-baseline gap-2 mb-2">
          <span className={`text-lg font-bold ${ratingColor}`}>{rating}</span>
          {totalScore != null && <span className="text-sm text-gray-400 font-data">{totalScore}/100</span>}
        </div>
      )}
      {radarData && radarData.some(d => d.score > 0) && (
        <GreenStarRadar data={radarData} />
      )}
      <div className="grid grid-cols-2 gap-1.5 mt-2">
        {solar?.system_kw != null && (
          <StatBox label="Solar System" value={`${solar.system_kw} kWp`} sub={solar.annual_kwh ? `${fmt(Math.round(solar.annual_kwh))} kWh/yr` : undefined} />
        )}
        {solar?.payback_years != null && (
          <StatBox label="Payback" value={`${solar.payback_years} yrs`} sub={solar.netzero_ratio ? `${Math.round(solar.netzero_ratio * 100)}% net zero` : undefined} />
        )}
        {water?.annual_harvest_litres != null && (
          <StatBox label="Rainwater" value={`${fmt(Math.round(water.annual_harvest_litres / 1000))} kl/yr`} sub={water.demand_met_pct ? `${Math.round(water.demand_met_pct)}% demand met` : undefined} />
        )}
        {water?.recommended_tank_litres != null && (
          <StatBox label="Tank Size" value={`${fmt(Math.round(water.recommended_tank_litres / 1000))} kl`} />
        )}
      </div>
    </CardWrapper>
  );
}

// --- Comparison ---
function ComparisonResultCard({ data }) {
  const radius = data.radius;
  const suburb = data.suburb;
  const source = radius || suburb;
  if (!source) return null;

  const label = radius ? `${radius.radius_km || 1} km radius` : 'suburb';
  const cheapest = source.cheapest;
  const expensive = source.most_expensive;
  const stats = source.statistics || source.stats;

  return (
    <CardWrapper icon={BarChart3} title={`Property Comparison (${label})`}>
      {source.property_value != null && (
        <div className="mb-2">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">This Property</div>
          <div className="text-lg font-bold text-white font-data">{fmtZar(source.property_value)}</div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-1.5">
        {cheapest && (
          <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-2">
            <div className="text-[10px] text-green-400 uppercase tracking-wider">Cheapest</div>
            <div className="text-sm font-bold text-green-400 font-data">{fmtZar(cheapest.market_value_zar || cheapest.value)}</div>
            {cheapest.rate_per_sqm && <div className="text-[10px] text-gray-500 font-data">{fmtZar(cheapest.rate_per_sqm)}/m²</div>}
          </div>
        )}
        {expensive && (
          <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-2">
            <div className="text-[10px] text-red-400 uppercase tracking-wider">Most Expensive</div>
            <div className="text-sm font-bold text-red-400 font-data">{fmtZar(expensive.market_value_zar || expensive.value)}</div>
            {expensive.rate_per_sqm && <div className="text-[10px] text-gray-500 font-data">{fmtZar(expensive.rate_per_sqm)}/m²</div>}
          </div>
        )}
      </div>
      {stats && (
        <div className="flex gap-3 mt-2 text-[11px] text-gray-400">
          {stats.median_value != null && <span>Median: <span className="text-white font-data">{fmtZar(stats.median_value)}</span></span>}
          {stats.count != null && <span>{stats.count} properties</span>}
        </div>
      )}
    </CardWrapper>
  );
}

// --- Constraint Map ---
function ConstraintMapCard({ data }) {
  const pct = data.developable_pct;
  if (pct == null) return null;
  const color = pct >= 70 ? '#22c55e' : pct >= 40 ? '#eab308' : '#ef4444';

  return (
    <CardWrapper icon={Map} title="Constraint Map Summary">
      <div className="space-y-2">
        <div className="flex items-baseline justify-between">
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">Developable Area</span>
          <span className="text-xl font-bold font-data" style={{ color }}>{Math.round(pct)}%</span>
        </div>
        <GaugeBar value={pct} max={100} color={color} />
        <div className="grid grid-cols-2 gap-1.5">
          {data.developable_area_sqm != null && <StatBox label="Developable" value={`${fmt(Math.round(data.developable_area_sqm))} m²`} />}
          {data.property_area_sqm != null && <StatBox label="Total Area" value={`${fmt(Math.round(data.property_area_sqm))} m²`} />}
        </div>
      </div>
    </CardWrapper>
  );
}

// --- Load Shedding ---
function LoadSheddingCard({ data }) {
  const riskLevel = data.risk_level || data.impact_level;
  const riskConf = riskLevel ? RISK_LEVEL_CONFIG[riskLevel] || {} : {};
  const stageImpacts = data.stage_impacts;

  const stageData = stageImpacts ? Object.entries(stageImpacts)
    .filter(([k]) => k.startsWith('stage_'))
    .map(([k, v]) => ({
      stage: parseInt(k.replace('stage_', '')),
      hours_per_day: v?.hours_per_day || v?.hours || (typeof v === 'number' ? v : 0),
    }))
    .sort((a, b) => a.stage - b.stage) : null;

  return (
    <CardWrapper icon={Battery} title="Load Shedding Impact">
      {riskLevel && (
        <div className="flex items-center gap-2 mb-2">
          <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${riskConf.bg || ''} ${riskConf.text || 'text-gray-300'} border ${riskConf.border || 'border-gray-700'}`}>
            {riskLevel} Risk
          </span>
          {data.block && <span className="text-[11px] text-gray-500">Block {data.block}</span>}
        </div>
      )}
      {data.baseline_impact != null && (
        <div className="space-y-1 mb-2">
          <div className="flex justify-between text-[10px]">
            <span className="text-gray-500">Baseline Impact</span>
            <span className="text-white font-data">{data.baseline_impact}/100</span>
          </div>
          <GaugeBar value={data.baseline_impact} max={100} color={riskConf.hex || '#eab308'} />
        </div>
      )}
      {stageData && stageData.length > 0 && <StageImpactChart data={stageData} />}
    </CardWrapper>
  );
}

// --- Crime ---
function CrimeResultCard({ data }) {
  const score = data.crime_score || data.risk_score;
  const riskLevel = data.risk_level;
  const riskConf = riskLevel ? RISK_LEVEL_CONFIG[riskLevel] || {} : {};
  const topCategories = data.top_categories || data.category_breakdown;
  const station = data.police_station || data.station_name;

  return (
    <CardWrapper icon={AlertTriangle} title="Crime Risk Assessment">
      <div className="flex items-center gap-3 mb-2">
        {riskLevel && (
          <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${riskConf.bg || ''} ${riskConf.text || 'text-gray-300'} border ${riskConf.border || 'border-gray-700'}`}>
            {riskLevel} Risk
          </span>
        )}
        {score != null && <span className="text-lg font-bold font-data" style={{ color: riskConf.hex || '#eab308' }}>{score}</span>}
        {score != null && <span className="text-[10px] text-gray-500">/100</span>}
      </div>
      {score != null && (
        <div className="mb-2">
          <GaugeBar value={score} max={100} color={riskConf.hex || '#eab308'} />
        </div>
      )}
      {station && <div className="text-[10px] text-gray-500 mb-2">Station: {station}</div>}
      {topCategories && topCategories.length > 0 && <CrimeBarChart data={topCategories} maxItems={5} />}
    </CardWrapper>
  );
}

// --- Municipal Health ---
function MunicipalCard({ data }) {
  const score = data.overall_score || data.health_score;
  const municipality = data.municipality;
  const trend = data.trend;
  const TrendIcon = trend === 'improving' ? TrendingUp : trend === 'declining' ? TrendingDown : Minus;
  const trendColor = trend === 'improving' ? 'text-green-400' : trend === 'declining' ? 'text-red-400' : 'text-gray-400';

  return (
    <CardWrapper icon={Building2} title="Municipal Health">
      {score != null && <HealthGauge score={score} />}
      <div className="flex items-center gap-3 mt-2 text-[11px] text-gray-400">
        {municipality && <span>{municipality}</span>}
        {data.financial_year && <span>{data.financial_year}</span>}
        {trend && (
          <span className={`flex items-center gap-1 ${trendColor}`}>
            <TrendIcon className="w-3 h-3" />
            {trend}
          </span>
        )}
      </div>
    </CardWrapper>
  );
}

// --- Development Potential ---
function DevelopmentPotentialCard({ data }) {
  const zoning = data.zoning || {};
  const site = data.site || {};
  const yld = data.yield || {};
  const constraints = data.constraints || [];
  const feasibility = data.feasibility || 'Unknown';

  const feasColors = {
    'Feasible': { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-400', icon: CheckCircle },
    'Constrained': { bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', text: 'text-yellow-400', icon: AlertTriangle },
    'Restricted': { bg: 'bg-orange-500/10', border: 'border-orange-500/30', text: 'text-orange-400', icon: AlertTriangle },
    'Not Feasible': { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', icon: XCircle },
  };
  const fc = feasColors[feasibility] || feasColors['Constrained'];
  const FeasIcon = fc.icon;

  const utilPct = site.site_utilization_pct || 0;
  const utilColor = utilPct >= 60 ? '#22c55e' : utilPct >= 30 ? '#eab308' : '#ef4444';

  return (
    <CardWrapper icon={Ruler} title="Development Potential">
      {/* Feasibility verdict */}
      <div className={`${fc.bg} border ${fc.border} rounded-lg p-2.5 flex items-center gap-2 mb-2`}>
        <FeasIcon className={`w-4 h-4 ${fc.text} shrink-0`} />
        <div>
          <div className={`text-sm font-semibold ${fc.text}`}>{feasibility}</div>
          {zoning.code && (
            <div className="text-[11px] text-gray-400">
              {zoning.code} — {zoning.name?.split(':')[0]?.trim() || zoning.rules?.zone_name}
            </div>
          )}
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 gap-1.5 mb-2">
        <StatBox label="Buildable Area" value={site.buildable_area_sqm ? `${fmt(Math.round(site.buildable_area_sqm))} m²` : '—'} />
        <StatBox label="Max GFA" value={yld.max_gfa_sqm ? `${fmt(Math.round(yld.max_gfa_sqm))} m²` : '—'} />
        <StatBox label="Est. Units" value={yld.estimated_units || '—'} sub={yld.development_type?.replace(/_/g, ' ')} />
        <StatBox label="Parking Bays" value={yld.required_parking_bays || '—'} sub={yld.parking_area_sqm ? `${fmt(yld.parking_area_sqm)} m²` : undefined} />
      </div>

      {/* Yield details */}
      <div className="flex gap-3 text-[11px] text-gray-400 mb-2">
        {yld.effective_floors && <span>Floors: <span className="text-white font-data">{yld.effective_floors}</span></span>}
        {zoning.rules?.far && <span>FAR: <span className="text-white font-data">{zoning.rules.far}</span></span>}
        {zoning.rules?.coverage_pct && <span>Coverage: <span className="text-white font-data">{zoning.rules.coverage_pct}%</span></span>}
      </div>

      {/* Site utilization gauge */}
      <div className="space-y-1 mb-2">
        <div className="flex justify-between text-[10px]">
          <span className="text-gray-500">Site Utilization</span>
          <span className="font-data" style={{ color: utilColor }}>{Math.round(utilPct)}%</span>
        </div>
        <GaugeBar value={utilPct} max={100} color={utilColor} />
      </div>

      {/* Constraints */}
      {constraints.length > 0 && (
        <div className="space-y-1 mt-2">
          {constraints.map((c, i) => {
            const sevColor = c.severity === 'critical' ? 'text-red-400' : c.severity === 'warning' ? 'text-yellow-400' : 'text-blue-400';
            const SevIcon = c.severity === 'critical' ? XCircle : c.severity === 'warning' ? AlertTriangle : Info;
            return (
              <div key={i} className="flex items-start gap-1.5 text-[11px]">
                <SevIcon className={`w-3 h-3 mt-0.5 shrink-0 ${sevColor}`} />
                <span className="text-gray-400">{c.message}</span>
              </div>
            );
          })}
        </div>
      )}
    </CardWrapper>
  );
}

// --- Main dispatcher ---
export default function ToolResultCard({ name, result }) {
  if (!result || result.error) return null;

  switch (name) {
    case 'search_property':           return <SearchResultCard data={result} />;
    case 'get_property_details':      return <PropertyDetailsCard data={result} />;
    case 'analyze_biodiversity':      return <BiodiversityCard data={result} />;
    case 'analyze_netzero':           return <NetZeroCard data={result} />;
    case 'compare_properties':        return <ComparisonResultCard data={result} />;
    case 'get_constraint_map':        return <ConstraintMapCard data={result} />;
    case 'get_loadshedding':          return <LoadSheddingCard data={result} />;
    case 'get_crime_stats':           return <CrimeResultCard data={result} />;
    case 'get_municipal_health':      return <MunicipalCard data={result} />;
    case 'get_development_potential': return <DevelopmentPotentialCard data={result} />;
    default: return null;
  }
}
