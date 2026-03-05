// CBA category → color + label mappings
export const CBA_COLORS = {
  'PA':     { fill: '#dc2626', stroke: '#991b1b', label: 'Protected Area' },
  'CA':     { fill: '#dc2626', stroke: '#991b1b', label: 'Conservation Area' },
  'CBA 1a': { fill: '#ef4444', stroke: '#b91c1c', label: 'CBA 1a (Irreplaceable)' },
  'CBA 1b': { fill: '#f97316', stroke: '#c2410c', label: 'CBA 1b (Irreplaceable, low condition)' },
  'CBA 1c': { fill: '#fb923c', stroke: '#ea580c', label: 'CBA 1c (Connectivity)' },
  'CBA 2':  { fill: '#f59e0b', stroke: '#b45309', label: 'CBA 2 (Optimal)' },
  'ESA 1':  { fill: '#eab308', stroke: '#a16207', label: 'ESA 1 (Natural/Semi-natural)' },
  'ESA 2':  { fill: '#facc15', stroke: '#ca8a04', label: 'ESA 2 (Modified)' },
  'ONA':    { fill: '#84cc16', stroke: '#4d7c0f', label: 'Other Natural Area' },
};

// Ecosystem threat status colors
export const THREAT_COLORS = {
  'CR': { fill: '#dc2626', label: 'Critically Endangered' },
  'EN': { fill: '#f97316', label: 'Endangered' },
  'VU': { fill: '#eab308', label: 'Vulnerable' },
  'LT': { fill: '#22c55e', label: 'Least Threatened' },
};

// Biodiversity status → badge styling
export const BIO_STATUS = {
  'no-go':      { color: 'bg-red-600',    text: 'text-white', label: 'No-Go' },
  'exceptional':{ color: 'bg-orange-500', text: 'text-white', label: 'Exceptional Only' },
  'offset':     { color: 'bg-amber-500',  text: 'text-gray-900', label: 'Offset Required' },
  'clear':      { color: 'bg-green-500',  text: 'text-white', label: 'No Constraints' },
};

// Green Star ratings
export const GREENSTAR_COLORS = {
  '6-star': 'text-emerald-400',
  '5-star': 'text-green-400',
  '4-star': 'text-lime-400',
  '3-star': 'text-yellow-400',
  'Below rated': 'text-gray-400',
};

// Technical term definitions for info tooltips
export const TERM_DEFINITIONS = {
  'CBA': 'Critical Biodiversity Area — land identified by the City of Cape Town BioNet as essential for meeting biodiversity targets. Categories range from CBA 1a (irreplaceable) to CBA 2 (optimal), with increasing flexibility for development.',
  'ESA': 'Ecological Support Area — land that supports the ecological functioning of Critical Biodiversity Areas. ESA 1 is natural/semi-natural; ESA 2 is already modified but still ecologically important.',
  'ONA': 'Other Natural Area — natural land that is not identified as a CBA or ESA. No offset requirements, but standard environmental screening may apply.',
  'PA': 'Protected Area — formally proclaimed under NEMPAA. Development is prohibited. These include nature reserves and national parks.',
  'CA': 'Conservation Area — informally protected land managed for biodiversity. Development is generally not permitted.',
  'Offset Ratio': 'The multiplier applied to the development footprint to calculate how much land must be conserved elsewhere. A 10:1 ratio means 10 hectares of conservation land for every 1 hectare developed.',
  'FAR': 'Floor Area Ratio — the ratio of total building floor area to the site area. A FAR of 2.0 on a 1,000 m² site allows up to 2,000 m² of gross floor area.',
  'Green Star': 'The Green Building Council of South Africa\'s rating system. Ranges from 3-star (Good Practice) to 6-star (World Leadership). Based on energy, water, ecology, location, and materials scores.',
  'Urban Edge': 'The City of Cape Town\'s urban development boundary. Properties outside the urban edge face stricter development controls and require exceptional motivation for development approval.',
  'NEMA': 'National Environmental Management Act (Act 107 of 1998) — South Africa\'s primary environmental legislation governing environmental impact assessments and biodiversity offsets.',
  'NHRA': 'National Heritage Resources Act (Act 25 of 1999) — governs the identification and protection of heritage resources. Section 34 requires permits for alterations to structures older than 60 years.',
  'Net Zero Ratio': 'The percentage of a building\'s annual energy consumption that can be offset by on-site renewable energy generation. 100% or above means the building can achieve net zero energy.',
  'Peak Sun Hours': 'The equivalent number of hours per day when solar irradiance averages 1,000 W/m². Cape Town averages 5.5 PSH/day — among the best in South Africa for solar generation.',
  'SSEG': 'Small-Scale Embedded Generation — the City of Cape Town\'s programme allowing properties to feed excess solar power back into the municipal grid for credits.',
  'Threat Status': 'SANBI ecosystem classification: CR (Critically Endangered), EN (Endangered), VU (Vulnerable), LT (Least Threatened). Higher threat status increases offset requirements.',
};

// Construction cost benchmarks (ZAR/m², Cape Town 2024/25)
export const CONSTRUCTION_COSTS = {
  residential_economic:  { label: 'Residential (Economic)', cost: 6500,  range: [5500, 8000] },
  residential_standard:  { label: 'Residential (Standard)', cost: 13150, range: [10000, 17000] },
  residential_high_end:  { label: 'Residential (High-end)', cost: 20000, range: [17000, 30000] },
  residential_luxury:    { label: 'Residential (Luxury)',    cost: 35000, range: [30000, 75000] },
  commercial_office:     { label: 'Commercial (Office)',     cost: 17500, range: [15000, 20000] },
  commercial_retail:     { label: 'Commercial (Retail)',     cost: 15000, range: [12000, 18000] },
  industrial:            { label: 'Industrial',              cost: 8000,  range: [6000, 12000] },
  mixed_use:             { label: 'Mixed Use',               cost: 15000, range: [12000, 20000] },
};

// Comparison marker colors
export const COMPARISON_COLORS = {
  cheapest: { fill: '#22c55e', stroke: '#15803d', label: 'Cheapest' },
  most_expensive: { fill: '#ef4444', stroke: '#b91c1c', label: 'Most Expensive' },
  radius: { fill: '#3b82f6', stroke: '#1d4ed8', opacity: 0.08 },
};

// Risk level → visual config
export const RISK_LEVEL_CONFIG = {
  Critical: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/30', dot: 'bg-red-500', hex: '#ef4444' },
  High:     { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30', dot: 'bg-orange-500', hex: '#f97316' },
  Medium:   { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/30', dot: 'bg-yellow-500', hex: '#eab308' },
  Low:      { bg: 'bg-green-500/15', text: 'text-green-400', border: 'border-green-500/30', dot: 'bg-green-500', hex: '#22c55e' },
};

// Load shedding stage colors (1-8)
export const STAGE_COLORS = {
  1: { bg: 'bg-yellow-200', text: 'text-yellow-900', hex: '#fef08a' },
  2: { bg: 'bg-yellow-300', text: 'text-yellow-900', hex: '#fde047' },
  3: { bg: 'bg-yellow-400', text: 'text-yellow-900', hex: '#facc15' },
  4: { bg: 'bg-amber-500', text: 'text-white', hex: '#f59e0b' },
  5: { bg: 'bg-orange-500', text: 'text-white', hex: '#f97316' },
  6: { bg: 'bg-red-500', text: 'text-white', hex: '#ef4444' },
  7: { bg: 'bg-red-600', text: 'text-white', hex: '#dc2626' },
  8: { bg: 'bg-red-800', text: 'text-white', hex: '#991b1b' },
};

// Municipal health score → color
export const MUNI_HEALTH_COLORS = {
  good:     { bg: 'bg-green-500/15', text: 'text-green-400', label: 'Good', hex: '#22c55e' },
  fair:     { bg: 'bg-yellow-500/15', text: 'text-yellow-400', label: 'Fair', hex: '#eab308' },
  poor:     { bg: 'bg-orange-500/15', text: 'text-orange-400', label: 'Poor', hex: '#f97316' },
  critical: { bg: 'bg-red-500/15', text: 'text-red-400', label: 'Critical', hex: '#ef4444' },
};

export function getMuniHealthLevel(score) {
  if (score >= 70) return 'good';
  if (score >= 50) return 'fair';
  if (score >= 30) return 'poor';
  return 'critical';
}

// Feasibility status colors
export const FEASIBILITY_COLORS = {
  'Feasible':       { bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/30' },
  'Constrained':    { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30' },
  'Restricted':     { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/30' },
  'Not Feasible':   { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' },
};

// Unit type colors for charts/visualization
export const UNIT_TYPE_COLORS = {
  studio:           '#a78bfa',
  '1bed':           '#818cf8',
  '2bed':           '#6366f1',
  '3bed':           '#4f46e5',
  house:            '#22c55e',
  townhouse_2bed:   '#34d399',
  townhouse_3bed:   '#10b981',
  townhouse_4bed:   '#059669',
  retail:           '#f59e0b',
  retail_ground:    '#f59e0b',
  office_small:     '#3b82f6',
  office_medium:    '#2563eb',
  warehouse_small:  '#64748b',
  warehouse_large:  '#475569',
  office_industrial:'#94a3b8',
};

// Premium suburbs where generic cost/revenue assumptions are likely inaccurate
export const LUXURY_SUBURBS = [
  'BANTRY BAY', 'CLIFTON', 'CAMPS BAY', 'LLANDUDNO', 'FRESNAYE',
  'CONSTANTIA', 'BISHOPSCOURT', 'HIGGOVALE', 'ORANJEZICHT',
  'CAMPS BAY', 'V&A WATERFRONT',
];

// Cape Town center
export const CT_CENTER = [-33.925, 18.475];
export const CT_ZOOM = 11;
