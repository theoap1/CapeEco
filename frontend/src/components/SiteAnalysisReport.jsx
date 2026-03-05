import { useState, useEffect, useRef } from 'react';
import {
  X, Download, Loader2, FileText, Building, Leaf, AlertTriangle,
  Info, Ruler, DollarSign, Zap,
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

function DataRow({ label, value }) {
  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-gray-100 dark:border-gray-800">
      <span className="text-sm text-gray-600 dark:text-gray-400">{label}</span>
      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{value ?? '—'}</span>
    </div>
  );
}

function SectionHeader({ title, icon: Icon }) {
  return (
    <div className="flex items-center gap-2 mb-3 pb-2 border-b-2 border-ocean-600">
      {Icon && <Icon className="w-5 h-5 text-ocean-600" />}
      <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
        {title}
      </h2>
    </div>
  );
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
      pdf.text(`Site Analysis — ERF ${property?.erf_number || ''}`, margin, pageHeight - 8);
      pdf.text(`Page ${page + 1} of ${totalPages}`, pageWidth - margin, pageHeight - 8, { align: 'right' });
    }

    const fileName = `SiteAnalysis_${property?.erf_number || 'report'}_${(property?.suburb || '').replace(/\s+/g, '_')}.pdf`;
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
// Main Component
// ───────────────────────────────────────────────────────────────────
export default function SiteAnalysisReport({ propertyId, mapImage, propertyGeometry, areaSqm, onClose }) {
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

  return (
    <div className="fixed inset-0 z-[2000] bg-black/60 flex items-center justify-center p-4 report-modal">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[95vh] flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 dark:border-gray-700
                        bg-gradient-to-r from-ocean-600 to-ocean-700 shrink-0">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-white" />
            <span className="text-sm font-semibold text-white">Site Analysis Report</span>
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
                <Loader2 className="w-8 h-8 animate-spin text-ocean-500 mx-auto mb-3" />
                <p className="text-sm text-gray-500">Generating site analysis...</p>
              </div>
            </div>
          ) : data ? (
            <div ref={contentRef} className="report-content max-w-[794px] mx-auto p-8 space-y-8">
              {/* Cover */}
              <div className="text-center border-b-2 border-ocean-600 pb-6">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wider">
                  Site Analysis Report
                </h1>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Development Feasibility &amp; Site Assessment
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
                      <span className="text-sm text-ocean-600 font-medium">{data.property.zoning}</span>
                    </>
                  )}
                </div>
                <p className="text-xs text-gray-400 mt-3">
                  Generated {new Date().toLocaleDateString('en-ZA', { day: 'numeric', month: 'long', year: 'numeric' })}
                </p>
              </div>

              {/* Property Summary */}
              <section className="report-section">
                <SectionHeader title="Property Summary" icon={Building} />
                <div className="grid grid-cols-2 gap-x-8">
                  <DataRow label="ERF Number" value={data.property.erf_number} />
                  <DataRow label="Suburb" value={data.property.suburb} />
                  <DataRow label="Site Area" value={fmtArea(data.property.area_sqm)} />
                  <DataRow label="Zoning" value={data.property.zoning || '—'} />
                  <DataRow label="Land Use" value={data.property.land_use_category || '—'} />
                  <DataRow label="Market Value" value={data.property.market_value_zar ? fmtZar(data.property.market_value_zar) : '—'} />
                </div>
              </section>

              {/* Site Map */}
              {mapImage && (
                <section className="report-section">
                  <SectionHeader title="Site Map" icon={Building} />
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

              {/* Dimensioned Boundary */}
              {(propertyGeometry || data.property?.geometry) && (
                <section className="report-section">
                  <SectionHeader title="Site Boundary & Dimensions" icon={Ruler} />
                  <SiteBoundaryDiagram
                    geometry={propertyGeometry || data.property?.geometry}
                    areaSqm={areaSqm || data.property?.area_sqm}
                  />
                </section>
              )}

              {/* Development Parameters */}
              {data.devPotential && (
                <section className="report-section">
                  <SectionHeader title="Development Parameters" icon={Building} />
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
                </section>
              )}

              {/* Massing Summary (Unit Mix) */}
              {data.devPotential?.unit_mix?.length > 0 && (
                <section className="report-section">
                  <SectionHeader title="Massing — Unit Mix" icon={Building} />
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
                </section>
              )}

              {/* Financials */}
              {data.devPotential?.financials && (
                <section className="report-section">
                  <SectionHeader title="Financial Feasibility" icon={DollarSign} />
                  <div className="grid grid-cols-2 gap-x-8">
                    <DataRow label="Total Dev Cost" value={fmtZar(data.devPotential.financials.total_development_cost)} />
                    <DataRow label="Estimated Revenue" value={fmtZar(data.devPotential.financials.estimated_revenue)} />
                    <DataRow label="Estimated Profit" value={fmtZar(data.devPotential.financials.estimated_profit)} />
                    <DataRow label="Margin" value={data.devPotential.financials.margin_pct ? `${data.devPotential.financials.margin_pct.toFixed(1)}%` : '—'} />
                    <DataRow label="ROI" value={data.devPotential.financials.roi_pct ? `${data.devPotential.financials.roi_pct.toFixed(1)}%` : '—'} />
                    <DataRow label="Cost per m² (GFA)" value={data.devPotential.financials.cost_per_sqm ? fmtZar(data.devPotential.financials.cost_per_sqm) : '—'} />
                  </div>
                </section>
              )}

              {/* Density Metrics */}
              {data.devPotential?.density && (
                <section className="report-section">
                  <SectionHeader title="Density Metrics" icon={Building} />
                  <div className="grid grid-cols-2 gap-x-8">
                    <DataRow label="Units per Hectare" value={data.devPotential.density.units_per_ha ? `${data.devPotential.density.units_per_ha.toFixed(1)}` : '—'} />
                    <DataRow label="Beds per Hectare" value={data.devPotential.density.beds_per_ha ? `${data.devPotential.density.beds_per_ha.toFixed(1)}` : '—'} />
                    <DataRow label="FAR Achieved" value={data.devPotential.density.far_achieved ? `${data.devPotential.density.far_achieved.toFixed(2)}` : '—'} />
                  </div>
                </section>
              )}

              {/* Energy & Sustainability */}
              {data.netzero && (
                <section className="report-section">
                  <SectionHeader title="Energy & Sustainability" icon={Zap} />
                  <div className="grid grid-cols-2 gap-x-8">
                    {data.netzero.solar && (
                      <>
                        <DataRow label="Solar System" value={data.netzero.solar.system_size_kwp ? `${data.netzero.solar.system_size_kwp} kWp` : '—'} />
                        <DataRow label="Annual Generation" value={data.netzero.solar.annual_generation_kwh ? `${fmt(data.netzero.solar.annual_generation_kwh)} kWh` : '—'} />
                        <DataRow label="Net Zero Ratio" value={data.netzero.solar.netzero_ratio_efficient ? `${(data.netzero.solar.netzero_ratio_efficient * 100).toFixed(0)}%` : '—'} />
                        <DataRow label="System Cost" value={data.netzero.solar.system_cost_zar ? fmtZar(data.netzero.solar.system_cost_zar) : '—'} />
                        <DataRow label="Payback" value={data.netzero.solar.payback_years ? `${data.netzero.solar.payback_years.toFixed(1)} years` : '—'} />
                      </>
                    )}
                    {data.netzero.scorecard && (
                      <DataRow label="Green Star Rating" value={data.netzero.scorecard.greenstar_rating ? `${data.netzero.scorecard.greenstar_rating} Star` : '—'} />
                    )}
                  </div>
                </section>
              )}

              {/* Environmental Constraints */}
              {data.biodiversity && (
                <section className="report-section">
                  <SectionHeader title="Environmental Constraints" icon={Leaf} />
                  <div className="grid grid-cols-2 gap-x-8">
                    <DataRow label="CBA Designation" value={data.biodiversity.designation || 'None'} />
                    <DataRow label="No-Go Zone" value={data.biodiversity.is_no_go ? 'Yes — development prohibited' : 'No'} />
                    <DataRow label="Offset Required" value={data.biodiversity.offset_applicable ? 'Yes' : 'No'} />
                    {data.biodiversity.offset_cost_low != null && (
                      <DataRow label="Offset Cost Range" value={`${fmtZar(data.biodiversity.offset_cost_low)} – ${fmtZar(data.biodiversity.offset_cost_high)}`} />
                    )}
                  </div>
                  {data.biodiversity.overlaps?.length > 0 && (
                    <div className="mt-3">
                      <h3 className="text-xs font-semibold text-gray-500 uppercase mb-1">Biodiversity Overlaps</h3>
                      {data.biodiversity.overlaps.map((o, i) => (
                        <div key={i} className="flex justify-between text-sm py-1 border-b border-gray-100 dark:border-gray-800">
                          <span className="text-gray-600 dark:text-gray-400">{o.cba_category || o.category}</span>
                          <span className="text-gray-900 dark:text-gray-100 font-medium">{o.overlap_pct ? `${o.overlap_pct.toFixed(1)}%` : o.overlap_area_sqm ? fmtArea(o.overlap_area_sqm) : '—'}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              )}

              {/* Notes */}
              {notes && (
                <section className="report-section">
                  <SectionHeader title="Notes" icon={Info} />
                  <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{notes}</p>
                </section>
              )}

              {/* Disclaimer */}
              <section className="report-section border-t-2 border-gray-200 dark:border-gray-700 pt-4 mt-8">
                <p className="text-xs text-gray-400 dark:text-gray-500 leading-relaxed">
                  <strong>Disclaimer:</strong> This site analysis report is a preliminary screening tool
                  generated by Siteline for development feasibility assessment. It does not constitute
                  professional architectural, engineering, town planning, or legal advice. All figures
                  are estimates based on zoning parameters and public data. Actual development outcomes
                  depend on detailed site investigation, municipal approvals, and professional design.
                  Verify all data independently before making investment decisions.
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
