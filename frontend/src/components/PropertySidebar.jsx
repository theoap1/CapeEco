import { useState, useEffect } from 'react';
import {
  X, ChevronRight, Sun, Droplets, Leaf, MapPin, Building, Ruler,
  Zap, Star, AlertTriangle, Shield, TrendingUp, Info, FileText,
} from 'lucide-react';
import { getProperty, getNetZeroAnalysis, getBiodiversityAnalysis, getConstraintMap, getPropertyReport } from '../utils/api';
import ReportView from './ReportView';
import { CBA_COLORS, BIO_STATUS, GREENSTAR_COLORS } from '../utils/constants';

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

export default function PropertySidebar({ propertyId, onClose, onShowConstraintMap }) {
  const [property, setProperty] = useState(null);
  const [netzero, setNetzero] = useState(null);
  const [biodiversity, setBiodiversity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisRun, setAnalysisRun] = useState(false);
  const [showReport, setShowReport] = useState(false);

  useEffect(() => {
    if (!propertyId) return;
    setLoading(true);
    setAnalysisRun(false);
    setNetzero(null);
    setBiodiversity(null);

    getProperty(propertyId)
      .then(setProperty)
      .catch(console.error)
      .finally(() => setLoading(false));
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
    <div className="w-full md:w-96 h-full bg-white dark:bg-gray-900 border-l border-gray-200
                    dark:border-gray-700 flex flex-col overflow-hidden shadow-xl">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between
                      bg-gradient-to-r from-ocean-600 to-ocean-700">
        <h2 className="text-sm font-semibold text-white truncate">Property Details</h2>
        <button onClick={onClose} className="text-white/70 hover:text-white transition-colors">
          <X className="w-5 h-5" />
        </button>
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
                onClick={() => setShowReport(true)}
                className="w-full mt-2 py-2 px-4 rounded-xl border border-protea-400 dark:border-protea-600
                           text-protea-700 dark:text-protea-300 text-sm hover:bg-protea-50 dark:hover:bg-protea-900/20
                           transition-colors flex items-center justify-center gap-2"
              >
                <Star className="w-4 h-4" />
                Generate Full Report
              </button>
            </div>
          )}

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
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
          Property not found
        </div>
      )}

      {showReport && (
        <ReportView propertyId={propertyId} onClose={() => setShowReport(false)} />
      )}
    </div>
  );
}
