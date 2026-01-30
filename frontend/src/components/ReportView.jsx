import { useState, useEffect, useRef, useCallback } from 'react';
import {
  X, Download, Loader2, AlertTriangle, Shield, Leaf, Sun, Droplets,
  Building, MapPin, Clock, ChevronRight, Star, FileText, Printer,
  Info, Sparkles, MessageSquare,
} from 'lucide-react';
import { getPropertyReport, getAiAnalysis } from '../utils/api';
import { CBA_COLORS, THREAT_COLORS, GREENSTAR_COLORS, TERM_DEFINITIONS } from '../utils/constants';
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

// ───────────────────────────────────────────────────────────────────
// Helpers
// ───────────────────────────────────────────────────────────────────
const fmt = (v) => v != null ? Number(v).toLocaleString('en-ZA') : '—';
const fmtZar = (v) => v != null ? `R ${Number(v).toLocaleString('en-ZA')}` : '—';
const fmtPct = (v) => v != null ? `${Number(v).toFixed(1)}%` : '—';
const fmtHa = (v) => v != null ? `${Number(v).toFixed(4)} ha` : '—';
const fmtArea = (v) => v != null ? `${Math.round(v).toLocaleString('en-ZA')} m²` : '—';

const RISK_STYLES = {
  Critical: { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-400', border: 'border-red-300 dark:border-red-700' },
  High:     { bg: 'bg-orange-100 dark:bg-orange-900/30', text: 'text-orange-700 dark:text-orange-400', border: 'border-orange-300 dark:border-orange-700' },
  Medium:   { bg: 'bg-amber-100 dark:bg-amber-900/30', text: 'text-amber-700 dark:text-amber-400', border: 'border-amber-300 dark:border-amber-700' },
  Low:      { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400', border: 'border-green-300 dark:border-green-700' },
};

const PRIORITY_LABELS = { 1: 'High', 2: 'Medium', 3: 'Low' };
const PRIORITY_COLORS = { 1: 'text-red-600', 2: 'text-amber-600', 3: 'text-green-600' };

// ───────────────────────────────────────────────────────────────────
// Sub-components
// ───────────────────────────────────────────────────────────────────
function ReportSection({ title, icon: Icon, children, className = '' }) {
  return (
    <section className={`report-section mb-6 ${className}`}>
      <div className="flex items-center gap-2 mb-3 pb-2 border-b-2 border-ocean-600">
        {Icon && <Icon className="w-5 h-5 text-ocean-600" />}
        <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 uppercase tracking-wide">
          {title}
        </h2>
      </div>
      {children}
    </section>
  );
}

function DataRow({ label, value, sub, bold = false }) {
  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-gray-100 dark:border-gray-800">
      <span className="text-sm text-gray-600 dark:text-gray-400">{label}</span>
      <div className="text-right">
        <span className={`text-sm ${bold ? 'font-bold' : 'font-medium'} text-gray-900 dark:text-gray-100`}>
          {value ?? '—'}
        </span>
        {sub && <div className="text-xs text-gray-400">{sub}</div>}
      </div>
    </div>
  );
}

function RiskBadge({ level }) {
  const s = RISK_STYLES[level] || RISK_STYLES.Low;
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-bold ${s.bg} ${s.text} border ${s.border}`}>
      {level === 'Critical' && <AlertTriangle className="w-4 h-4 mr-1.5" />}
      {level} Risk
    </span>
  );
}

const SCORE_DESCRIPTIONS = {
  Energy: 'On-site renewable generation vs. estimated building demand. Higher = closer to net zero energy.',
  Water: 'Rainwater harvesting potential relative to building water demand. Higher = greater self-sufficiency.',
  Ecology: 'Biodiversity sensitivity of the site. Higher = fewer environmental constraints on development.',
  Location: 'Proximity to public transport, amenities, and urban services. Higher = better connected.',
  Materials: 'Potential for sustainable materials and innovation credits. Based on building type and design scope.',
};

function ScoreGauge({ score, max, label, color }) {
  const pct = max > 0 ? Math.min((score / max) * 100, 100) : 0;
  const desc = SCORE_DESCRIPTIONS[label];
  const rating = pct >= 80 ? 'Excellent' : pct >= 60 ? 'Good' : pct >= 40 ? 'Fair' : 'Low';
  return (
    <div className="flex-1 text-center group relative">
      <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{score}<span className="text-sm text-gray-400">/{max}</span></div>
      <div className="mt-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mt-1">{label}</div>
      <div className="text-[10px] text-gray-400 mt-0.5">{rating}</div>
      {desc && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 z-50 bg-gray-900 text-gray-100 text-xs rounded-lg px-3 py-2 shadow-xl border border-gray-700 leading-relaxed opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
          <div className="font-bold text-ocean-300 mb-1">{label} ({max} pts max)</div>
          {desc}
          <div className="absolute top-full left-1/2 -translate-x-1/2 w-2 h-2 bg-gray-900 rotate-45 -mt-1 border-r border-b border-gray-700" />
        </div>
      )}
    </div>
  );
}

function BiodiversityTable({ designations }) {
  if (!designations?.length) {
    return <p className="text-sm text-gray-500 italic">No biodiversity designations overlay this property.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 dark:bg-gray-800">
            <th className="text-left px-3 py-2 font-semibold text-gray-700 dark:text-gray-300">Designation</th>
            <th className="text-right px-3 py-2 font-semibold text-gray-700 dark:text-gray-300">Overlap</th>
            <th className="text-right px-3 py-2 font-semibold text-gray-700 dark:text-gray-300">Area</th>
            <th className="text-center px-3 py-2 font-semibold text-gray-700 dark:text-gray-300">Status</th>
            <th className="text-center px-3 py-2 font-semibold text-gray-700 dark:text-gray-300">Offset Ratio<InfoTooltip term="Offset Ratio" /></th>
          </tr>
        </thead>
        <tbody>
          {designations.map((d, i) => {
            const c = CBA_COLORS[d.designation];
            return (
              <tr key={i} className="border-b border-gray-100 dark:border-gray-800">
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: c?.fill || '#9ca3af' }} />
                    <div>
                      <div className="font-medium text-gray-900 dark:text-gray-100">{d.designation}</div>
                      <div className="text-xs text-gray-400">{d.name}</div>
                    </div>
                  </div>
                </td>
                <td className="px-3 py-2 text-right font-medium">{fmtPct(d.overlap_pct)}</td>
                <td className="px-3 py-2 text-right">{fmtHa(d.affected_area_ha)}</td>
                <td className="px-3 py-2 text-center">
                  {d.is_no_go ? (
                    <span className="text-xs font-bold text-red-600">NO-GO</span>
                  ) : d.offset_applicable ? (
                    <span className="text-xs font-bold text-amber-600">OFFSET</span>
                  ) : (
                    <span className="text-xs text-gray-400">—</span>
                  )}
                </td>
                <td className="px-3 py-2 text-center">
                  {d.base_ratio != null ? `${d.base_ratio}:1` : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ActionItemsTable({ items }) {
  if (!items?.length) return null;
  return (
    <div className="space-y-3">
      {items.map((item, i) => (
        <div key={i} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 border-l-4"
             style={{ borderLeftColor: item.priority === 1 ? '#dc2626' : item.priority === 2 ? '#f59e0b' : '#22c55e' }}>
          <div className="flex items-start justify-between mb-1">
            <div className="flex items-center gap-2">
              <span className={`text-xs font-bold ${PRIORITY_COLORS[item.priority]}`}>
                {PRIORITY_LABELS[item.priority]} Priority
              </span>
              <span className="text-xs bg-gray-200 dark:bg-gray-700 px-1.5 py-0.5 rounded text-gray-600 dark:text-gray-400">
                {item.category}
              </span>
            </div>
            {item.timeline_days > 0 && (
              <span className="text-xs text-gray-400 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                ~{item.timeline_days} days
              </span>
            )}
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300">{item.action}</p>
          {item.specialist && (
            <p className="text-xs text-gray-400 mt-1">Specialist: {item.specialist}</p>
          )}
        </div>
      ))}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// Info Tooltip — hover to see definition of a technical term
// ───────────────────────────────────────────────────────────────────
function InfoTooltip({ term }) {
  const [open, setOpen] = useState(false);
  const def = TERM_DEFINITIONS[term];
  if (!def) return null;
  return (
    <span className="relative inline-flex items-center ml-1 align-middle">
      <button
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onClick={() => setOpen(o => !o)}
        className="text-ocean-400 hover:text-ocean-600 transition-colors"
        aria-label={`Info about ${term}`}
      >
        <Info className="w-3.5 h-3.5" />
      </button>
      {open && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 z-50 bg-gray-900 text-gray-100 text-xs rounded-lg px-3 py-2 shadow-xl border border-gray-700 leading-relaxed pointer-events-none">
          <div className="font-bold text-ocean-300 mb-1">{term}</div>
          {def}
          <div className="absolute top-full left-1/2 -translate-x-1/2 w-2 h-2 bg-gray-900 rotate-45 -mt-1 border-r border-b border-gray-700" />
        </div>
      )}
    </span>
  );
}

// ───────────────────────────────────────────────────────────────────
// AI Insight — auto-loads analysis for a report section
// ───────────────────────────────────────────────────────────────────
function AiInsight({ section, context, autoLoad = true }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const fetched = useRef(false);

  const fetchAnalysis = useCallback(() => {
    if (loading || analysis) return;
    setLoading(true);
    setError(null);
    getAiAnalysis(section, context)
      .then(res => {
        if (res.analysis) setAnalysis(res.analysis);
        else if (res.error) setError(res.error);
      })
      .catch(() => setError('AI unavailable'))
      .finally(() => setLoading(false));
  }, [section, context, loading, analysis]);

  useEffect(() => {
    if (autoLoad && !fetched.current) {
      fetched.current = true;
      fetchAnalysis();
    }
  }, [autoLoad, fetchAnalysis]);

  if (!autoLoad && !analysis && !loading) return null;

  return (
    <div className="mt-3 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-950/30 dark:to-purple-950/30 border border-indigo-200 dark:border-indigo-800 rounded-xl p-3">
      <div className="flex items-center gap-1.5 mb-1.5">
        <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
        <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">AI Insight</span>
      </div>
      {loading && (
        <div className="flex items-center gap-2 text-xs text-indigo-400">
          <Loader2 className="w-3 h-3 animate-spin" /> Analysing…
        </div>
      )}
      {error && <p className="text-xs text-gray-400 italic">{error}</p>}
      {analysis && <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{analysis}</p>}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// Ask AI Button — on-demand analysis trigger
// ───────────────────────────────────────────────────────────────────
function AskAiButton({ section, context, label = 'Ask AI' }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleClick = () => {
    if (loading || analysis) return;
    setLoading(true);
    setError(null);
    getAiAnalysis(section, context)
      .then(res => {
        if (res.analysis) setAnalysis(res.analysis);
        else if (res.error) setError(res.error);
      })
      .catch(() => setError('AI unavailable'))
      .finally(() => setLoading(false));
  };

  return (
    <div className="mt-3">
      {!analysis && (
        <button
          onClick={handleClick}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-100 dark:bg-indigo-900/40 hover:bg-indigo-200 dark:hover:bg-indigo-800/50 text-indigo-700 dark:text-indigo-300 text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <MessageSquare className="w-3 h-3" />}
          {loading ? 'Analysing…' : label}
        </button>
      )}
      {error && <p className="text-xs text-gray-400 italic mt-1">{error}</p>}
      {analysis && (
        <div className="bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-950/30 dark:to-purple-950/30 border border-indigo-200 dark:border-indigo-800 rounded-xl p-3">
          <div className="flex items-center gap-1.5 mb-1.5">
            <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
            <span className="text-xs font-semibold text-indigo-600 dark:text-indigo-400">AI Analysis</span>
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{analysis}</p>
        </div>
      )}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────
// PDF Export
// ───────────────────────────────────────────────────────────────────
async function exportToPDF(contentRef, reportData) {
  const el = contentRef.current;
  if (!el) return;

  // Temporarily remove dark mode for PDF (print as light)
  const wasDark = el.closest('.dark') !== null;
  const root = document.documentElement;
  if (wasDark) root.classList.remove('dark');

  // Add print class for styling adjustments
  el.classList.add('printing');

  // Temporarily expand the scroll container so html2canvas captures all content
  const scrollParent = el.closest('.report-content-wrapper');
  const modalBox = el.closest('.max-h-\\[95vh\\]');
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

    // Capture at high DPI
    const canvas = await html2canvas(el, {
      scale: 2,
      useCORS: true,
      logging: false,
      backgroundColor: '#ffffff',
      windowWidth: 794, // A4 at 96dpi
      scrollY: -window.scrollY,
    });

    const imgWidth = contentWidth;
    const imgHeight = (canvas.height * imgWidth) / canvas.width;
    const totalPages = Math.ceil(imgHeight / usableHeight);

    for (let page = 0; page < totalPages; page++) {
      if (page > 0) pdf.addPage();

      // Clip and draw portion of canvas for this page
      const srcY = page * (canvas.width * usableHeight / imgWidth);
      const srcH = canvas.width * usableHeight / imgWidth;

      const pageCanvas = document.createElement('canvas');
      pageCanvas.width = canvas.width;
      pageCanvas.height = Math.min(srcH, canvas.height - srcY);

      const ctx = pageCanvas.getContext('2d');
      ctx.drawImage(canvas, 0, srcY, canvas.width, pageCanvas.height, 0, 0, pageCanvas.width, pageCanvas.height);

      const pageImgHeight = (pageCanvas.height * imgWidth) / pageCanvas.width;
      pdf.addImage(pageCanvas.toDataURL('image/png'), 'PNG', margin, margin, imgWidth, pageImgHeight);

      // Footer
      pdf.setFontSize(7);
      pdf.setTextColor(150);
      pdf.text(`CapeEco Development Potential Report — ${reportData.report_id}`, margin, pageHeight - 8);
      pdf.text(`Page ${page + 1} of ${totalPages}`, pageWidth - margin, pageHeight - 8, { align: 'right' });
      pdf.text('CONFIDENTIAL — For authorised use only', pageWidth / 2, pageHeight - 8, { align: 'center' });
    }

    const fileName = `CapeEco_Report_${reportData.property.erf_number}_${reportData.property.suburb.replace(/\s+/g, '_')}.pdf`;
    pdf.save(fileName);
  } finally {
    // Restore scroll container styles
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
export default function ReportView({ propertyId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);
  const contentRef = useRef(null);

  useEffect(() => {
    if (!propertyId) return;
    setLoading(true);
    setError(null);
    getPropertyReport(propertyId)
      .then(setData)
      .catch(e => setError(e.response?.data?.detail || 'Failed to generate report'))
      .finally(() => setLoading(false));
  }, [propertyId]);

  const handleExport = async () => {
    if (!data) return;
    setExporting(true);
    try {
      await exportToPDF(contentRef, data);
    } catch (e) {
      console.error('PDF export failed:', e);
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-[2000] bg-black/50 flex items-center justify-center">
        <div className="bg-white dark:bg-gray-900 rounded-2xl p-8 flex flex-col items-center gap-4 shadow-2xl">
          <Loader2 className="w-10 h-10 text-ocean-500 animate-spin" />
          <p className="text-gray-600 dark:text-gray-400 font-medium">Generating report…</p>
          <p className="text-xs text-gray-400">Aggregating biodiversity, heritage, zoning, and net zero data</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 z-[2000] bg-black/50 flex items-center justify-center">
        <div className="bg-white dark:bg-gray-900 rounded-2xl p-8 max-w-md shadow-2xl">
          <div className="flex items-center gap-2 text-red-600 mb-3">
            <AlertTriangle className="w-6 h-6" />
            <h3 className="font-bold text-lg">Report Error</h3>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">{error}</p>
          <button onClick={onClose} className="px-4 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg text-sm font-medium hover:bg-gray-200 dark:hover:bg-gray-700">
            Close
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { property, executive_summary: exec, biodiversity: bio, heritage, zoning_analysis: zoning,
          netzero, action_items, disclaimer } = data;
  const sc = netzero?.scorecard;
  const sol = netzero?.solar;
  const wat = netzero?.water;

  return (
    <div className="fixed inset-0 z-[2000] bg-black/50 flex items-center justify-center p-4 report-modal">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[95vh] flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-ocean-600 to-ocean-700 shrink-0">
          <div className="flex items-center gap-3 text-white">
            <FileText className="w-5 h-5" />
            <span className="font-semibold">Development Potential Report</span>
            <span className="text-xs text-white/60">{data.report_id}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleExport}
              disabled={exporting}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-lg text-white text-sm font-medium transition-colors disabled:opacity-50"
            >
              {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              {exporting ? 'Exporting…' : 'Export PDF'}
            </button>
            <button
              onClick={() => window.print()}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-lg text-white text-sm font-medium transition-colors"
            >
              <Printer className="w-4 h-4" />
              Print
            </button>
            <button onClick={onClose} className="text-white/70 hover:text-white transition-colors ml-2">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Report Content (scrollable) */}
        <div className="flex-1 overflow-y-auto sidebar-scroll report-content-wrapper">
          <div ref={contentRef} className="report-content max-w-[794px] mx-auto p-8 space-y-6">

            {/* ─── HEADER / COVER ─── */}
            <div className="text-center pb-6 border-b-2 border-ocean-600">
              <div className="flex items-center justify-center gap-2 mb-4">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-ocean-500 to-protea-600 flex items-center justify-center">
                  <Leaf className="w-5 h-5 text-white" />
                </div>
              </div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 tracking-tight">
                Development Potential Report
              </h1>
              <p className="text-sm text-gray-500 mt-1">Environmental, Heritage & Net Zero Assessment</p>
              <div className="mt-4 text-sm text-gray-600 dark:text-gray-400">
                <p className="font-semibold text-gray-900 dark:text-gray-100">
                  ERF {property.erf_number}, {property.suburb}
                </p>
                <p>{property.address}</p>
                <p className="mt-1 text-xs text-gray-400">Report Date: {data.report_date} · {data.report_id}</p>
              </div>
            </div>

            {/* ─── EXECUTIVE SUMMARY ─── */}
            <ReportSection title="Executive Summary" icon={FileText}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-3 text-center">
                  <div className="text-xs text-gray-400 uppercase tracking-wider">Area</div>
                  <div className="text-lg font-bold text-gray-900 dark:text-gray-100 mt-1">{fmtArea(property.area_sqm)}</div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-3 text-center">
                  <div className="text-xs text-gray-400 uppercase tracking-wider">Bio Risk</div>
                  <div className="mt-1"><RiskBadge level={exec.biodiversity_risk} /></div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-3 text-center">
                  <div className="text-xs text-gray-400 uppercase tracking-wider">Developable</div>
                  <div className="text-lg font-bold text-gray-900 dark:text-gray-100 mt-1">{fmtPct(exec.developable_area_pct)}</div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-3 text-center">
                  <div className="text-xs text-gray-400 uppercase tracking-wider">Green Star</div>
                  <div className={`text-lg font-bold mt-1 ${GREENSTAR_COLORS[exec.greenstar_rating] || 'text-gray-400'}`}>
                    {exec.greenstar_rating || '—'}
                  </div>
                </div>
              </div>

              <div className="bg-ocean-50 dark:bg-ocean-900/20 border border-ocean-200 dark:border-ocean-800 rounded-xl p-4">
                <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                  ERF {property.erf_number} ({property.suburb}) is a <strong>{fmtArea(property.area_sqm)}</strong> property
                  zoned <strong>{property.zoning?.split(':')[0]?.trim() || 'unclassified'}</strong>,
                  situated <strong>{property.inside_urban_edge ? 'inside' : 'outside'}</strong> the
                  Cape Town urban edge.
                  {bio.designations?.length > 0 ? (
                    <> The site carries <strong>{exec.biodiversity_risk.toLowerCase()}</strong> biodiversity risk
                    with {bio.designations.length} designation{bio.designations.length > 1 ? 's' : ''} affecting {fmtPct(bio.total_constrained_pct)} of
                    the property, leaving {fmtPct(exec.developable_area_pct)} developable.</>
                  ) : (
                    <> No significant biodiversity designations overlay the property, making it a <strong>low-risk</strong> development site from an ecological perspective.</>
                  )}
                  {exec.netzero_score != null && (
                    <> The net zero screening score is <strong>{exec.netzero_score}/100</strong> ({exec.greenstar_rating}).</>
                  )}
                  {exec.offset_cost_range && (
                    <> Estimated biodiversity offset costs range from <strong>{exec.offset_cost_range.formatted_low}</strong> to <strong>{exec.offset_cost_range.formatted_high}</strong>.</>
                  )}
                </p>
              </div>

              <AiInsight section="executive_summary" context={{
                erf: property.erf_number, suburb: property.suburb, area_sqm: property.area_sqm,
                zoning: property.zoning, inside_urban_edge: property.inside_urban_edge,
                bio_risk: exec.biodiversity_risk, developable_pct: exec.developable_area_pct,
                greenstar: exec.greenstar_rating, netzero_score: exec.netzero_score,
                offset_cost: exec.offset_cost_range,
              }} />
            </ReportSection>

            {/* ─── PROPERTY DETAILS ─── */}
            <ReportSection title="Property Details" icon={MapPin}>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
                <div>
                  <DataRow label="ERF Number" value={property.erf_number} />
                  <DataRow label="Address" value={property.address} />
                  <DataRow label="Suburb" value={property.suburb} />
                  <DataRow label="Site Area" value={fmtArea(property.area_sqm)} sub={property.area_ha ? `${property.area_ha} ha` : null} />
                </div>
                <div>
                  <DataRow label="Zoning" value={property.zoning?.split(':')[0]?.trim()} sub={property.zoning?.includes(':') ? property.zoning.split(':')[1]?.trim() : null} />
                  <DataRow label={<>Urban Edge<InfoTooltip term="Urban Edge" /></>} value={property.inside_urban_edge ? 'Inside' : 'Outside'} />
                  <DataRow label="Coordinates" value={property.coordinates ? `${property.coordinates.lat?.toFixed(5)}°S, ${property.coordinates.lon?.toFixed(5)}°E` : '—'} />
                </div>
              </div>
            </ReportSection>

            {/* ─── ZONING ANALYSIS ─── */}
            {zoning && (
              <ReportSection title="Zoning Parameters" icon={Building}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
                  <div>
                    <DataRow label="Classification" value={zoning.zoning_classification?.split(':')[0]?.trim()} />
                    <DataRow label="Max Height" value={zoning.max_height_m ? `${zoning.max_height_m} m` : '—'} />
                    <DataRow label="Max Floors" value={zoning.max_floors ?? '—'} />
                    <DataRow label="Max Coverage" value={zoning.max_coverage_pct ? `${zoning.max_coverage_pct}%` : '—'} />
                  </div>
                  <div>
                    <DataRow label={<>Floor Area Ratio (FAR)<InfoTooltip term="FAR" /></>} value={zoning.floor_area_ratio ?? '—'} />
                    <DataRow label="Max Footprint" value={zoning.max_footprint_sqm ? fmtArea(zoning.max_footprint_sqm) : '—'} />
                    <DataRow label="Max GFA" value={zoning.max_gfa_sqm ? fmtArea(zoning.max_gfa_sqm) : '—'} bold />
                  </div>
                </div>
              </ReportSection>
            )}

            {/* ─── BIODIVERSITY ─── */}
            <ReportSection title={<>Biodiversity Assessment<InfoTooltip term="CBA" /></>} icon={Leaf}>
              <div className="flex items-center gap-4 mb-4">
                <RiskBadge level={exec.biodiversity_risk} />
                <span className="text-sm text-gray-500">
                  {bio.total_constrained_pct > 0
                    ? `${fmtPct(bio.total_constrained_pct)} constrained · ${fmtPct(bio.developable_pct)} developable`
                    : 'No overlapping biodiversity designations'}
                </span>
              </div>

              <BiodiversityTable designations={bio.designations} />

              {/* Ecosystems */}
              {bio.ecosystems?.length > 0 && (
                <div className="mt-4">
                  <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Ecosystem Types</h3>
                  <div className="flex flex-wrap gap-2">
                    {bio.ecosystems.map((e, i) => {
                      const tc = THREAT_COLORS[e.threat_status];
                      return (
                        <span key={i} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
                          {tc && <span className="w-2 h-2 rounded-full" style={{ backgroundColor: tc.fill }} />}
                          {e.vegetation_type}
                          {e.threat_status && <span className="font-bold" style={{ color: tc?.fill }}>({e.threat_status})</span>}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Offset analysis */}
              {bio.offset_analysis && bio.offset_analysis.offset_applicable && (
                <div className="mt-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4">
                  <h3 className="text-sm font-bold text-amber-800 dark:text-amber-400 mb-2">Biodiversity Offset Requirement</h3>
                  <div className="grid grid-cols-2 gap-x-6 text-sm">
                    <DataRow label="Designation" value={bio.offset_analysis.designation} />
                    <DataRow label="Base Ratio" value={`${bio.offset_analysis.base_ratio}:1`} />
                    <DataRow label="Condition Multiplier" value={`×${bio.offset_analysis.condition_multiplier}`} />
                    <DataRow label="Urban Edge Adj." value={`×${bio.offset_analysis.urban_edge_adjustment}`} />
                    <DataRow label="Final Ratio" value={`${bio.offset_analysis.final_ratio}:1`} />
                    <DataRow label="Dev. Footprint" value={`${bio.offset_analysis.development_footprint_ha?.toFixed(4)} ha`} />
                    <DataRow label="Required Offset" value={`${bio.offset_analysis.required_offset_ha?.toFixed(4)} ha`} bold />
                    {bio.offset_analysis.offset_cost_estimate_zar > 0 && (
                      <DataRow label="Est. Cost" value={fmtZar(bio.offset_analysis.offset_cost_estimate_zar)} bold />
                    )}
                  </div>
                </div>
              )}

              {/* No-go warning */}
              {bio.designations?.some(d => d.is_no_go) && (
                <div className="mt-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-4">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
                    <div>
                      <h3 className="text-sm font-bold text-red-700 dark:text-red-400">No-Go Zone</h3>
                      <p className="text-sm text-red-600 dark:text-red-300 mt-1">
                        This property overlaps with a Protected Area, Conservation Area, or CBA 1a.
                        Development is not permitted in these areas. The relevant portion must be excluded
                        from any development layout.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Descriptions for each designation */}
              {bio.designations?.length > 0 && (
                <div className="mt-4 space-y-2">
                  {bio.designations.map((d, i) => d.description && (
                    <div key={i} className="text-xs text-gray-500 dark:text-gray-400 pl-3 border-l-2 border-gray-200 dark:border-gray-700">
                      <span className="font-medium text-gray-600 dark:text-gray-300">{d.designation}:</span> {d.description}
                    </div>
                  ))}
                </div>
              )}

              <AiInsight section="biodiversity" context={{
                designations: bio.designations?.map(d => ({ designation: d.designation, overlap_pct: d.overlap_pct, is_no_go: d.is_no_go, offset_applicable: d.offset_applicable })),
                ecosystems: bio.ecosystems,
                total_constrained_pct: bio.total_constrained_pct,
                developable_pct: bio.developable_pct,
                risk_level: exec.biodiversity_risk,
              }} />
            </ReportSection>

            {/* ─── HERITAGE ─── */}
            {heritage?.has_heritage && (
              <ReportSection title={`Heritage Assessment (${heritage.count} record${heritage.count !== 1 ? 's' : ''})`} icon={Shield}>
                <div className="space-y-2">
                  {heritage.sites.map((h, i) => (
                    <div key={i} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 flex items-start justify-between">
                      <div>
                        <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          {h.site_name || (h.source === 'nhra' ? 'NHRA Protected Site' : 'Heritage Inventory Record')}
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5 space-y-0.5">
                          {h.heritage_category != null && <div>Category: {h.heritage_category}</div>}
                          {h.city_grading && h.city_grading !== 'Not Set' && <div>City Grading: {h.city_grading}</div>}
                          {h.architectural_style && <div>Style: {h.architectural_style}</div>}
                          {h.period && <div>Period: {h.period}</div>}
                          {h.nhra_status && <div>NHRA Status: {h.nhra_status}</div>}
                        </div>
                      </div>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full shrink-0 ${
                        h.source === 'nhra' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                      }`}>
                        {h.source === 'nhra' ? 'NHRA' : 'Inventory'}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-400 mt-3">
                  Heritage sites within 100m of the property boundary. Section 34 of the NHRA<InfoTooltip term="NHRA" /> requires a permit for
                  demolition or alteration of structures older than 60 years. Contact Heritage Western Cape for guidance.
                </p>

                <AiInsight section="heritage" context={{
                  sites: heritage.sites?.map(h => ({ name: h.site_name, source: h.source, category: h.heritage_category, grading: h.city_grading, nhra_status: h.nhra_status })),
                  count: heritage.count,
                }} />
              </ReportSection>
            )}

            {/* ─── NET ZERO / GREEN STAR ─── */}
            {sc && (
              <ReportSection title={<>Net Zero & Green Star Assessment<InfoTooltip term="Green Star" /></>} icon={Star}>
                <div className="text-center mb-4">
                  <div className={`text-4xl font-bold ${GREENSTAR_COLORS[sc.greenstar_rating] || 'text-gray-400'}`}>
                    {sc.greenstar_rating}
                  </div>
                  <div className="text-sm text-gray-500 mt-1">{sc.greenstar_label}</div>
                  <div className="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">
                    {sc.total_score}/100
                  </div>
                </div>

                <p className="text-xs text-gray-500 dark:text-gray-400 mb-3 text-center">
                  Score breakdown across five Green Star SA categories. Each category is weighted by its maximum points — hover for details.
                </p>
                <div className="flex gap-4 mb-6">
                  <ScoreGauge score={sc.scores.energy} max={35} label="Energy" color="bg-amber-500" />
                  <ScoreGauge score={sc.scores.water} max={25} label="Water" color="bg-blue-500" />
                  <ScoreGauge score={sc.scores.ecology} max={20} label="Ecology" color="bg-green-500" />
                  <ScoreGauge score={sc.scores.location} max={10} label="Location" color="bg-purple-500" />
                  <ScoreGauge score={sc.scores.materials_innovation} max={10} label="Materials" color="bg-gray-500" />
                </div>

                <AiInsight section="netzero" context={{
                  total_score: sc.total_score, greenstar_rating: sc.greenstar_rating,
                  scores: sc.scores, greenstar_label: sc.greenstar_label,
                }} />

                {/* Solar details */}
                {sol && (
                  <div className="mt-4">
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
                      <Sun className="w-4 h-4 text-amber-500" /> Solar Potential<InfoTooltip term="Peak Sun Hours" />
                    </h3>
                    <div className="grid grid-cols-2 gap-x-8">
                      <DataRow label="System Size" value={`${sol.system_size_kwp} kWp`} />
                      <DataRow label="Annual Generation" value={`${fmt(Math.round(sol.annual_generation_kwh))} kWh`} />
                      <DataRow label={<>Net Zero Ratio<InfoTooltip term="Net Zero Ratio" /></>} value={`${(sol.netzero_ratio_average * 100).toFixed(0)}%`}
                               sub={sol.netzero_energy_feasible ? 'Net Zero feasible' : 'Below target'} />
                      <DataRow label="Carbon Offset" value={`${sol.carbon_offset_tonnes_per_year} t CO₂/yr`} />
                      <DataRow label="Estimated Floors" value={sol.estimated_floors ?? '—'} />
                      <DataRow label="Estimated GFA" value={sol.estimated_gfa_sqm ? fmtArea(sol.estimated_gfa_sqm) : '—'} />
                      <DataRow label="Payback Period" value={sol.estimated_payback_years ? `${sol.estimated_payback_years} years` : '—'} />
                    </div>
                    <AskAiButton section="solar" label="Ask AI about solar potential" context={{
                      system_size_kwp: sol.system_size_kwp, annual_kwh: sol.annual_generation_kwh,
                      netzero_ratio: sol.netzero_ratio_average, feasible: sol.netzero_energy_feasible,
                      carbon_offset: sol.carbon_offset_tonnes_per_year, payback_years: sol.estimated_payback_years,
                      estimated_floors: sol.estimated_floors, estimated_gfa: sol.estimated_gfa_sqm,
                    }} />
                  </div>
                )}

                {/* Water details */}
                {wat && (
                  <div className="mt-4">
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
                      <Droplets className="w-4 h-4 text-blue-500" /> Water Harvesting
                    </h3>
                    <div className="grid grid-cols-2 gap-x-8">
                      <DataRow label="Rainfall Zone" value={wat.rainfall_zone || '—'} />
                      <DataRow label="Annual Rainfall" value={`${wat.annual_rainfall_mm || '—'} mm`} />
                      <DataRow label="Annual Harvest" value={`${wat.annual_harvestable_kl} kl`} />
                      <DataRow label="Demand Met" value={`${wat.demand_met_pct}%`} />
                      <DataRow label="Recommended Tank" value={`${wat.recommended_tank_size_kl} kl`} />
                    </div>
                    <AskAiButton section="water" label="Ask AI about water resilience" context={{
                      rainfall_zone: wat.rainfall_zone, annual_mm: wat.annual_rainfall_mm,
                      annual_harvest_kl: wat.annual_harvestable_kl, demand_met_pct: wat.demand_met_pct,
                      tank_size_kl: wat.recommended_tank_size_kl,
                    }} />
                  </div>
                )}
              </ReportSection>
            )}

            {/* ─── ACTION ITEMS ─── */}
            {action_items?.length > 0 && (
              <ReportSection title="Recommended Actions" icon={ChevronRight}>
                <ActionItemsTable items={action_items} />
                <AiInsight section="actions" context={{
                  actions: action_items.map(a => ({ priority: a.priority, category: a.category, action: a.action, timeline_days: a.timeline_days })),
                  bio_risk: exec.biodiversity_risk,
                }} />
              </ReportSection>
            )}

            {/* ─── DISCLAIMER ─── */}
            <div className="mt-8 pt-4 border-t border-gray-200 dark:border-gray-700">
              <p className="text-[10px] text-gray-400 leading-relaxed">
                <strong>DISCLAIMER:</strong> {disclaimer || 'This report is a desktop-level screening assessment based on publicly available spatial data from the City of Cape Town Open Data Portal. It does not constitute a formal Environmental Impact Assessment, Heritage Impact Assessment, or any other statutory assessment. All findings should be verified by suitably qualified professionals before making investment or development decisions. Offset cost estimates are indicative only and subject to market conditions. CapeEco accepts no liability for decisions made based on this report.'}
              </p>
              <p className="text-[10px] text-gray-400 mt-2">
                Data sources: City of Cape Town BioNet (2023), CCT Heritage Resources Audit, CCT Open Data Portal, NHRA Register.
                Solar calculations based on Cape Town average 5.5 PSH/day. Energy benchmarks per SANS 10400-XA.
                Water demand per SANS 10252-1.
              </p>
              <div className="flex items-center justify-between mt-4 pt-2 border-t border-gray-100 dark:border-gray-800">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-ocean-500 to-protea-600 flex items-center justify-center">
                    <Leaf className="w-3 h-3 text-white" />
                  </div>
                  <span className="text-xs font-bold text-gray-400">CapeEco</span>
                </div>
                <span className="text-[10px] text-gray-400">Generated {data.report_date}</span>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
