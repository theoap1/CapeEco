import { useState, useEffect, useRef } from 'react';
import {
  X, Download, Loader2, Shield, Building, Flame, Wind, Droplets,
  Accessibility, Zap, CheckCircle, AlertTriangle, Info,
} from 'lucide-react';
import {
  getProperty, getDevelopmentPotential, getConstraintMap,
  getMassing, getNetZeroAnalysis, getBiodiversityAnalysis,
} from '../utils/api';
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';
import SiteBoundaryDiagram from './SiteBoundaryDiagram';

// ───────────────────────────────────────────────────────────────────
// Helpers
// ───────────────────────────────────────────────────────────────────
const fmt = (v) => v != null ? Number(v).toLocaleString('en-ZA') : '—';
const fmtZar = (v) => v != null ? `R ${Number(v).toLocaleString('en-ZA')}` : '—';
const fmtArea = (v) => v != null ? `${Math.round(v).toLocaleString('en-ZA')} m²` : '—';

function StatusIcon({ status }) {
  if (status === 'pass') return <CheckCircle className="w-4 h-4 text-green-600" />;
  if (status === 'warning') return <AlertTriangle className="w-4 h-4 text-amber-500" />;
  return <Info className="w-4 h-4 text-gray-400" />;
}

// ───────────────────────────────────────────────────────────────────
// SANS 10400 Part Definitions
// ───────────────────────────────────────────────────────────────────
function classifyOccupancy(devPotential) {
  const type = devPotential?.yield?.development_type || '';
  if (type.includes('commercial') || type.includes('office')) return 'G1 — Offices';
  if (type.includes('retail') || type.includes('shop')) return 'A1 — Entertainment/Public Assembly';
  if (type.includes('mixed')) return 'Mixed (H4/G1)';
  if (type.includes('high')) return 'H4 — Dwelling House (4+ storeys)';
  if (type.includes('medium')) return 'H3 — Domestic Residence';
  return 'H4 — Dwelling House';
}

function getSANSParts(devPotential, property, netzero) {
  const floors = devPotential?.yield?.effective_floors || 1;
  const gfa = devPotential?.yield?.max_gfa_sqm || 0;
  const units = devPotential?.yield?.estimated_units || 0;
  const coveragePct = devPotential?.zoning?.rules?.coverage_pct || 50;
  const isResidential = !devPotential?.yield?.development_type?.includes('commercial');
  const heightLimit = devPotential?.zoning?.rules?.height_limit || 0;
  const parkingSolution = devPotential?.parking?.recommended_solution || 'surface';
  const totalBays = devPotential?.parking?.total_bays || 0;

  return [
    {
      code: 'A',
      title: 'General Principles & Requirements',
      icon: Building,
      description: 'Application scope, classification of buildings by occupancy class, and determination of applicable deemed-to-satisfy rules.',
      checks: [
        { item: 'Occupancy Classification', value: classifyOccupancy(devPotential), status: 'info' },
        { item: 'Deemed-to-Satisfy Applicability', value: floors <= 4 ? 'Applicable — standard rules apply' : 'Rational Design Required (>4 storeys)', status: floors <= 4 ? 'pass' : 'warning' },
        { item: 'Building Classification', value: floors <= 3 ? 'Class 1 — Small building' : 'Class 2 — Large building', status: 'info' },
      ],
    },
    {
      code: 'B',
      title: 'Structural Design',
      icon: Building,
      description: 'Structural integrity requirements for the proposed building height, type, and loading conditions per SANS 10160.',
      checks: [
        { item: 'Max Building Height', value: `${heightLimit}m`, status: 'info' },
        { item: 'Number of Floors', value: `${floors}`, status: 'info' },
        { item: 'Structural System', value: floors > 4 ? 'Reinforced Concrete Frame required' : 'Load-bearing Masonry or Light Frame', status: floors > 4 ? 'warning' : 'info' },
        { item: 'Wind Loading Region', value: 'Region A (Cape Town coastal) — enhanced wind design', status: 'warning' },
        { item: 'Seismic Zone', value: 'Zone I (low seismicity) — standard design', status: 'pass' },
      ],
    },
    {
      code: 'T',
      title: 'Fire Protection',
      icon: Flame,
      description: 'Fire safety requirements including fire resistance ratings, escape routes, sprinkler systems, and fire department access.',
      checks: [
        { item: 'Fire Resistance Rating', value: floors >= 4 ? '120 min (multi-storey)' : floors >= 2 ? '60 min' : '30 min', status: floors >= 4 ? 'warning' : 'pass' },
        { item: 'Sprinkler System', value: floors >= 4 || gfa > 2500 ? 'Required' : 'Not Required', status: floors >= 4 || gfa > 2500 ? 'warning' : 'pass' },
        { item: 'Fire Department Access', value: floors >= 4 ? 'Aerial appliance access required' : 'Standard access', status: floors >= 4 ? 'warning' : 'info' },
        { item: 'Emergency Egress', value: floors >= 2 ? `2+ escape routes required` : '1 escape route sufficient', status: 'info' },
        { item: 'Fire Detection', value: floors >= 2 || units > 4 ? 'Automatic detection system required' : 'Smoke detectors per unit', status: 'info' },
      ],
    },
    {
      code: 'G',
      title: 'Excavation & Foundation',
      icon: Building,
      description: 'Foundation design requirements based on soil conditions, excavation depths, and building loads.',
      checks: [
        { item: 'Geotechnical Investigation', value: floors > 2 || gfa > 500 ? 'Required before design' : 'Recommended', status: floors > 2 ? 'warning' : 'info' },
        { item: 'Foundation Type', value: floors > 3 ? 'Engineered (raft/pile) — engineer design required' : 'Strip/pad foundations may suffice', status: floors > 3 ? 'warning' : 'info' },
      ],
    },
    {
      code: 'K',
      title: 'Walls',
      icon: Building,
      description: 'Wall construction requirements including structural adequacy, weather resistance, and thermal performance.',
      checks: [
        { item: 'Wall Construction', value: floors <= 2 ? 'Single-leaf masonry (190mm)' : 'Cavity or reinforced masonry', status: 'info' },
        { item: 'Weather Resistance', value: 'Face brick or plastered — Cape Town moderate exposure zone', status: 'info' },
        { item: 'Thermal Insulation', value: isResidential ? 'R-value 0.35 min (walls) per SANS 10400-XA' : 'Per rational design', status: 'info' },
      ],
    },
    {
      code: 'O',
      title: 'Lighting & Ventilation',
      icon: Wind,
      description: 'Natural lighting and ventilation requirements for habitable rooms, ensuring adequate air quality and daylight.',
      checks: [
        { item: 'Natural Light', value: 'Min 10% of floor area as glazing', status: 'info' },
        { item: 'Natural Ventilation', value: 'Min 5% of floor area openable', status: 'info' },
        { item: 'Habitable Rooms', value: 'Direct ventilation to outside required', status: 'info' },
        { item: 'Parking Areas', value: parkingSolution === 'basement' ? 'Mechanical ventilation system required' : 'Natural ventilation adequate', status: parkingSolution === 'basement' ? 'warning' : 'pass' },
      ],
    },
    {
      code: 'N',
      title: 'Drainage',
      icon: Droplets,
      description: 'Stormwater management, drainage requirements, and rainwater disposal per municipal by-laws.',
      checks: [
        { item: 'Stormwater Detention', value: coveragePct > 50 ? 'Required (>50% impervious)' : 'Recommended', status: coveragePct > 50 ? 'warning' : 'info' },
        { item: 'Estimated Impervious Area', value: fmtArea((property?.area_sqm || 0) * coveragePct / 100), status: 'info' },
        { item: 'Sewer Connection', value: 'Municipal sewer — capacity confirmation required', status: 'info' },
      ],
    },
    {
      code: 'S',
      title: 'Facilities for Persons with Disabilities',
      icon: Accessibility,
      description: 'Universal access requirements ensuring buildings are accessible to persons with disabilities.',
      checks: [
        { item: 'Accessible Units', value: units > 4 ? `Min ${Math.max(1, Math.ceil(units * 0.05))} units (5%) must be accessible` : 'Not required for <5 units', status: units > 4 ? 'warning' : 'info' },
        { item: 'Common Area Access', value: units > 4 ? 'Level access + lifts if >1 storey' : 'N/A', status: units > 4 ? 'info' : 'info' },
        { item: 'Accessible Parking', value: units > 4 ? `Min ${Math.max(1, Math.ceil(totalBays * 0.02))} designated bays` : 'N/A', status: 'info' },
        { item: 'Ramps & Doorways', value: units > 4 ? 'Min 850mm doors, max 1:12 ramp gradient' : 'Standard', status: 'info' },
      ],
    },
    {
      code: 'XA',
      title: 'Energy Usage in Buildings',
      icon: Zap,
      description: 'Energy performance requirements per SANS 10400-XA:2021, including benchmarks, solar potential, and net-zero readiness.',
      checks: [
        { item: 'Energy Benchmark', value: isResidential ? '50 kWh/m²/yr (SANS 10400-XA compliant)' : '120 kWh/m²/yr (commercial)', status: 'info' },
        { item: 'Annual Energy Demand (Efficient)', value: `${fmt(Math.round(gfa * (isResidential ? 50 : 120)))} kWh`, status: 'info' },
        { item: 'Solar PV Potential', value: netzero?.solar?.system_size_kwp ? `${netzero.solar.system_size_kwp} kWp system` : 'Not assessed', status: netzero?.solar?.netzero_ratio_efficient >= 1.0 ? 'pass' : 'info' },
        { item: 'Net Zero Ratio', value: netzero?.solar?.netzero_ratio_efficient ? `${(netzero.solar.netzero_ratio_efficient * 100).toFixed(0)}%` : 'N/A', status: netzero?.solar?.netzero_ratio_efficient >= 1.0 ? 'pass' : 'warning' },
        { item: 'Green Star Rating', value: netzero?.scorecard?.greenstar_rating ? `${netzero.scorecard.greenstar_rating} Star` : 'N/A', status: 'info' },
        { item: 'Hot Water', value: isResidential ? 'Min 50% from solar/heat pump (XA requirement)' : 'Heat recovery recommended', status: 'warning' },
        { item: 'Ceiling Insulation', value: isResidential ? 'R-value 3.70 min (SANS 10400-XA)' : 'Per rational design', status: 'info' },
      ],
    },
  ];
}

// ───────────────────────────────────────────────────────────────────
// PDF Export
// ───────────────────────────────────────────────────────────────────
async function exportToPDF(contentRef, property) {
  const el = contentRef.current;
  if (!el) return;

  const wasDark = el.closest('.dark') !== null;
  const root = document.documentElement;
  if (wasDark) root.classList.remove('dark');
  el.classList.add('printing');

  const scrollParent = el.closest('.report-content-wrapper');
  const modalBox = scrollParent?.parentElement;
  const savedStyles = [];
  for (const node of [scrollParent, modalBox]) {
    if (node) {
      savedStyles.push({ node, maxHeight: node.style.maxHeight, overflow: node.style.overflow, height: node.style.height });
      node.style.maxHeight = 'none';
      node.style.overflow = 'visible';
      node.style.height = 'auto';
    }
  }

  try {
    const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    const pageWidth = 210;
    const pageHeight = 297;
    const margin = 15;
    const contentWidth = pageWidth - (margin * 2);
    const usableHeight = pageHeight - (margin * 2);

    const canvas = await html2canvas(el, {
      scale: 2,
      useCORS: true,
      logging: false,
      backgroundColor: '#ffffff',
      windowWidth: 794,
      scrollY: -window.scrollY,
    });

    const imgWidth = contentWidth;
    const imgHeight = (canvas.height * imgWidth) / canvas.width;
    const totalPages = Math.ceil(imgHeight / usableHeight);

    for (let page = 0; page < totalPages; page++) {
      if (page > 0) pdf.addPage();

      const srcY = page * (canvas.width * usableHeight / imgWidth);
      const srcH = canvas.width * usableHeight / imgWidth;

      const pageCanvas = document.createElement('canvas');
      pageCanvas.width = canvas.width;
      pageCanvas.height = Math.min(srcH, canvas.height - srcY);

      const ctx = pageCanvas.getContext('2d');
      ctx.drawImage(canvas, 0, srcY, canvas.width, pageCanvas.height, 0, 0, pageCanvas.width, pageCanvas.height);

      const pageImgHeight = (pageCanvas.height * imgWidth) / pageCanvas.width;
      pdf.addImage(pageCanvas.toDataURL('image/png'), 'PNG', margin, margin, imgWidth, pageImgHeight);

      pdf.setFontSize(7);
      pdf.setTextColor(150);
      pdf.text(`SANS 10400 Compliance Screening — ERF ${property?.erf_number || ''}`, margin, pageHeight - 8);
      pdf.text(`Page ${page + 1} of ${totalPages}`, pageWidth - margin, pageHeight - 8, { align: 'right' });
      pdf.text('SCREENING ONLY — Not a substitute for professional assessment', pageWidth / 2, pageHeight - 8, { align: 'center' });
    }

    const fileName = `SANS10400_${property?.erf_number || 'report'}_${(property?.suburb || '').replace(/\s+/g, '_')}.pdf`;
    pdf.save(fileName);
  } finally {
    for (const { node, maxHeight, overflow, height } of savedStyles) {
      node.style.maxHeight = maxHeight;
      node.style.overflow = overflow;
      node.style.height = height;
    }
    el.classList.remove('printing');
    if (wasDark) root.classList.add('dark');
  }
}

// ───────────────────────────────────────────────────────────────────
// Sub-components
// ───────────────────────────────────────────────────────────────────
function SectionHeader({ code, title, icon: Icon, description }) {
  return (
    <div className="mb-3">
      <div className="flex items-center gap-2 pb-2 border-b-2 border-fynbos-600">
        {Icon && <Icon className="w-5 h-5 text-fynbos-600" />}
        <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
          Part {code}: {title}
        </h2>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1.5">{description}</p>
    </div>
  );
}

function ComplianceTable({ checks }) {
  return (
    <table className="w-full text-sm sans-compliance-table">
      <thead>
        <tr className="border-b border-gray-200 dark:border-gray-700">
          <th className="text-left py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Requirement</th>
          <th className="text-right py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Assessment</th>
          <th className="w-8 py-2"></th>
        </tr>
      </thead>
      <tbody>
        {checks.map((check, i) => (
          <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
            <td className="py-2.5 text-gray-600 dark:text-gray-400">{check.item}</td>
            <td className="py-2.5 text-right font-medium text-gray-900 dark:text-gray-100">{check.value}</td>
            <td className="py-2.5 pl-2">
              <StatusIcon status={check.status} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DataRow({ label, value }) {
  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-gray-100 dark:border-gray-800">
      <span className="text-sm text-gray-600 dark:text-gray-400">{label}</span>
      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{value ?? '—'}</span>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// Main Component
// ───────────────────────────────────────────────────────────────────
export default function SANSComplianceReport({ propertyId, mapImage, propertyGeometry, areaSqm, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [notes, setNotes] = useState('');
  const contentRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    Promise.all([
      getProperty(propertyId),
      getDevelopmentPotential(propertyId),
      getConstraintMap(propertyId).catch(() => null),
      getMassing(propertyId).catch(() => null),
      getNetZeroAnalysis(propertyId).catch(() => null),
      getBiodiversityAnalysis(propertyId, 500).catch(() => null),
    ]).then(([property, devPotential, constraintMap, massing, netzero, biodiversity]) => {
      if (!cancelled) {
        setData({ property, devPotential, constraintMap, massing, netzero, biodiversity });
      }
    }).catch(console.error)
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [propertyId]);

  const handleExport = async () => {
    setExporting(true);
    try {
      await exportToPDF(contentRef, data?.property);
    } catch (err) {
      console.error('PDF export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  const sansParts = data ? getSANSParts(data.devPotential, data.property, data.netzero) : [];

  // Count status types for summary
  const allChecks = sansParts.flatMap(p => p.checks);
  const warningCount = allChecks.filter(c => c.status === 'warning').length;
  const passCount = allChecks.filter(c => c.status === 'pass').length;

  return (
    <div className="fixed inset-0 z-[2000] bg-black/60 flex items-center justify-center p-4 report-modal">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[95vh] flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 dark:border-gray-700
                        bg-gradient-to-r from-fynbos-600 to-fynbos-700 shrink-0">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-white" />
            <span className="text-sm font-semibold text-white">SANS 10400 Compliance Screening</span>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Add notes..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="px-2 py-1 rounded-lg text-xs bg-white/15 text-white placeholder-white/50
                         border border-white/20 focus:outline-none focus:border-white/40 w-48"
            />
            <button
              onClick={handleExport}
              disabled={loading || exporting}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
                         bg-white/15 hover:bg-white/25 text-white transition-colors disabled:opacity-50"
            >
              {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              Export PDF
            </button>
            <button onClick={onClose} className="text-white/70 hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto sidebar-scroll report-content-wrapper">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-center">
                <Loader2 className="w-8 h-8 animate-spin text-fynbos-500 mx-auto mb-3" />
                <p className="text-sm text-gray-500">Generating compliance screening...</p>
              </div>
            </div>
          ) : data ? (
            <div ref={contentRef} className="report-content sans-report-content max-w-[794px] mx-auto p-8 space-y-8">
              {/* Cover / Header */}
              <div className="text-center border-b-2 border-fynbos-600 pb-6">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wider">
                  SANS 10400 Compliance Screening
                </h1>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  National Building Regulations & Standards
                </p>
                <div className="mt-4 inline-flex items-center gap-3 bg-gray-100 dark:bg-gray-800 rounded-lg px-4 py-2">
                  <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                    ERF {data.property.erf_number}
                  </span>
                  <span className="text-gray-400">|</span>
                  <span className="text-sm text-gray-500">{data.property.suburb}</span>
                  {data.property.zoning && (
                    <>
                      <span className="text-gray-400">|</span>
                      <span className="text-sm text-fynbos-600 font-medium">{data.property.zoning}</span>
                    </>
                  )}
                </div>
                <p className="text-xs text-gray-400 mt-3">
                  Generated {new Date().toLocaleDateString('en-ZA', { day: 'numeric', month: 'long', year: 'numeric' })}
                </p>
              </div>

              {/* Property Summary */}
              <section className="report-section">
                <div className="flex items-center gap-2 mb-3 pb-2 border-b-2 border-fynbos-600">
                  <Building className="w-5 h-5 text-fynbos-600" />
                  <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
                    Property Summary
                  </h2>
                </div>
                <div className="grid grid-cols-2 gap-x-8">
                  <DataRow label="ERF Number" value={data.property.erf_number} />
                  <DataRow label="Suburb" value={data.property.suburb} />
                  <DataRow label="Site Area" value={fmtArea(data.property.area_sqm)} />
                  <DataRow label="Zoning" value={data.property.zoning || '—'} />
                  <DataRow label="Land Use" value={data.property.land_use_category || '—'} />
                  <DataRow label="Market Value" value={data.property.market_value_zar ? fmtZar(data.property.market_value_zar) : '—'} />
                </div>
              </section>

              {/* Site Map Capture */}
              {mapImage && (
                <section className="report-section">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b-2 border-fynbos-600">
                    <Building className="w-5 h-5 text-fynbos-600" />
                    <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
                      Site Map
                    </h2>
                  </div>
                  <img
                    src={mapImage}
                    alt="Site map capture"
                    className="w-full rounded-lg border border-gray-200 dark:border-gray-700"
                  />
                  <p className="text-[10px] text-gray-400 mt-1">
                    Map capture showing current overlays at time of report generation.
                  </p>
                </section>
              )}

              {/* Dimensioned Site Boundary */}
              {(propertyGeometry || data.property?.geometry) && (
                <section className="report-section">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b-2 border-fynbos-600">
                    <Building className="w-5 h-5 text-fynbos-600" />
                    <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
                      Site Boundary &amp; Dimensions
                    </h2>
                  </div>
                  <SiteBoundaryDiagram
                    geometry={propertyGeometry || data.property?.geometry}
                    areaSqm={areaSqm || data.property?.area_sqm}
                  />
                </section>
              )}

              {/* Development Potential Summary */}
              {data.devPotential && (
                <section className="report-section">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b-2 border-fynbos-600">
                    <Building className="w-5 h-5 text-fynbos-600" />
                    <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
                      Development Parameters
                    </h2>
                  </div>
                  <div className="grid grid-cols-2 gap-x-8">
                    <DataRow label="Development Type" value={data.devPotential.yield?.development_type || '—'} />
                    <DataRow label="Max Floors" value={data.devPotential.zoning?.rules?.max_floors || '—'} />
                    <DataRow label="Height Limit" value={data.devPotential.zoning?.rules?.height_limit ? `${data.devPotential.zoning.rules.height_limit}m` : '—'} />
                    <DataRow label="Coverage" value={data.devPotential.zoning?.rules?.coverage_pct ? `${data.devPotential.zoning.rules.coverage_pct}%` : '—'} />
                    <DataRow label="FAR" value={data.devPotential.zoning?.rules?.far ?? '—'} />
                    <DataRow label="GFA" value={data.devPotential.yield?.max_gfa_sqm ? fmtArea(data.devPotential.yield.max_gfa_sqm) : '—'} />
                    <DataRow label="Estimated Units" value={data.devPotential.yield?.estimated_units || '—'} />
                    <DataRow label="Total Parking" value={data.devPotential.parking?.total_bays ? `${data.devPotential.parking.total_bays} bays` : '—'} />
                    <DataRow label="Parking Solution" value={data.devPotential.parking?.recommended_solution || '—'} />
                    <DataRow label="Feasibility" value={data.devPotential.constraints?.feasibility_flag || '—'} />
                  </div>

                  {/* Unit Mix */}
                  {data.devPotential.unit_mix?.length > 0 && (
                    <div className="mt-4">
                      <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Unit Mix</h3>
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-200 dark:border-gray-700">
                            <th className="text-left py-1.5 text-xs font-semibold text-gray-500 uppercase">Type</th>
                            <th className="text-right py-1.5 text-xs font-semibold text-gray-500 uppercase">Count</th>
                            <th className="text-right py-1.5 text-xs font-semibold text-gray-500 uppercase">Size</th>
                            <th className="text-right py-1.5 text-xs font-semibold text-gray-500 uppercase">Share</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.devPotential.unit_mix.filter(u => u.count > 0).map((u, i) => (
                            <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                              <td className="py-1.5 text-gray-700 dark:text-gray-300">{u.label}</td>
                              <td className="py-1.5 text-right text-gray-900 dark:text-gray-100 font-medium">{u.count}</td>
                              <td className="py-1.5 text-right text-gray-500">{u.avg_sqm ? `${u.avg_sqm} m²` : '—'}</td>
                              <td className="py-1.5 text-right text-gray-500">{u.share_pct ? `${u.share_pct.toFixed(0)}%` : '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Financials */}
                  {data.devPotential.financials && (
                    <div className="mt-4">
                      <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Financial Feasibility</h3>
                      <div className="grid grid-cols-2 gap-x-8">
                        <DataRow label="Total Dev Cost" value={fmtZar(data.devPotential.financials.total_development_cost)} />
                        <DataRow label="Estimated Revenue" value={fmtZar(data.devPotential.financials.estimated_revenue)} />
                        <DataRow label="Estimated Profit" value={fmtZar(data.devPotential.financials.estimated_profit)} />
                        <DataRow label="Margin" value={data.devPotential.financials.margin_pct ? `${data.devPotential.financials.margin_pct.toFixed(1)}%` : '—'} />
                      </div>
                    </div>
                  )}
                </section>
              )}

              {/* Biodiversity Constraints */}
              {data.biodiversity && (
                <section className="report-section">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b-2 border-fynbos-600">
                    <AlertTriangle className="w-5 h-5 text-fynbos-600" />
                    <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
                      Environmental Constraints
                    </h2>
                  </div>
                  <div className="grid grid-cols-2 gap-x-8">
                    <DataRow label="CBA Designation" value={data.biodiversity.designation || 'None'} />
                    <DataRow label="No-Go Zone" value={data.biodiversity.is_no_go ? 'Yes — development prohibited' : 'No'} />
                    <DataRow label="Offset Required" value={data.biodiversity.offset_applicable ? 'Yes' : 'No'} />
                    {data.biodiversity.offset_cost_low != null && (
                      <DataRow label="Offset Cost Range" value={`${fmtZar(data.biodiversity.offset_cost_low)} – ${fmtZar(data.biodiversity.offset_cost_high)}`} />
                    )}
                  </div>
                </section>
              )}

              {/* Compliance Summary */}
              <section className="report-section">
                <div className="flex items-center gap-2 mb-3 pb-2 border-b-2 border-fynbos-600">
                  <Shield className="w-5 h-5 text-fynbos-600" />
                  <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
                    Compliance Summary
                  </h2>
                </div>
                <div className="flex items-center gap-6 mb-4">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <span className="text-sm text-gray-700 dark:text-gray-300">{passCount} items compliant</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-amber-500" />
                    <span className="text-sm text-gray-700 dark:text-gray-300">{warningCount} items require attention</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Info className="w-5 h-5 text-gray-400" />
                    <span className="text-sm text-gray-700 dark:text-gray-300">{allChecks.length - passCount - warningCount} informational</span>
                  </div>
                </div>
              </section>

              {/* SANS 10400 Parts */}
              {sansParts.map((part) => (
                <section key={part.code} className="report-section">
                  <SectionHeader
                    code={part.code}
                    title={part.title}
                    icon={part.icon}
                    description={part.description}
                  />
                  <ComplianceTable checks={part.checks} />
                </section>
              ))}

              {/* Notes */}
              {notes && (
                <section className="report-section">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b-2 border-fynbos-600">
                    <Info className="w-5 h-5 text-fynbos-600" />
                    <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
                      Notes
                    </h2>
                  </div>
                  <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{notes}</p>
                </section>
              )}

              {/* Disclaimer */}
              <section className="report-section border-t-2 border-gray-200 dark:border-gray-700 pt-4 mt-8">
                <p className="text-xs text-gray-400 dark:text-gray-500 leading-relaxed">
                  <strong>Disclaimer:</strong> This is a preliminary screening tool only and does not constitute
                  professional architectural, engineering, or legal advice. SANS 10400 compliance must be
                  verified by a registered professional (architect, engineer, or building inspector) during
                  the formal building plan submission process. Actual compliance requirements may differ based
                  on detailed site conditions, municipal by-laws, and the final building design. This report
                  is generated by Siteline for development screening purposes and should be used as a guide
                  for early-stage feasibility assessment only.
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-2">
                  Reference: SANS 10400:2011 (as amended), National Building Regulations and Building Standards Act, 1977 (Act 103 of 1977).
                </p>
              </section>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64">
              <p className="text-sm text-gray-500">Failed to load property data.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
