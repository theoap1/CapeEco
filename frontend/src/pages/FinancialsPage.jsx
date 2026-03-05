import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, DollarSign, TrendingUp, AlertTriangle, CheckCircle2, XCircle,
  Building2, Loader2, Info,
} from 'lucide-react';
import { getProperty, getDevelopmentPotential } from '../utils/api';
import { UNIT_TYPE_COLORS, LUXURY_SUBURBS } from '../utils/constants';
import { RevenueBarChart } from '../components/AnalysisCharts';

// ── Helpers ────────────────────────────────────────────────────────────
function fmtR(val) {
  if (val == null) return '—';
  const abs = Math.abs(val);
  if (abs >= 1e9) return `R ${(val / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `R ${(val / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `R ${(val / 1e3).toFixed(0)}K`;
  return `R ${val.toLocaleString()}`;
}

function fmtRFull(val) {
  if (val == null) return '—';
  return `R ${val.toLocaleString()}`;
}

function pct(val) {
  if (val == null) return '—';
  return `${val.toFixed(1)}%`;
}

function marginColor(m) {
  if (m >= 20) return { text: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/30', hex: '#22c55e' };
  if (m >= 15) return { text: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', hex: '#eab308' };
  return { text: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30', hex: '#ef4444' };
}

// ── Section Card ───────────────────────────────────────────────────────
function Section({ title, icon: Icon, children }) {
  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-2xl overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800 flex items-center gap-2">
        {Icon && <Icon className="w-4 h-4 text-ocean-400" />}
        <h2 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

// ── Formula Block ──────────────────────────────────────────────────────
function Formula({ children }) {
  return (
    <div className="bg-gray-800/40 rounded-lg px-3 py-2 font-mono text-[10px] text-gray-500 mt-3">
      {children}
    </div>
  );
}

// ── Metric Card ────────────────────────────────────────────────────────
function MetricCard({ label, value, sub, color }) {
  return (
    <div className="bg-gray-800/60 border border-gray-700/50 rounded-xl p-4">
      <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-xl font-bold font-data ${color || 'text-gray-100'}`}>{value}</div>
      {sub && <div className="text-[10px] text-gray-500 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Spreadsheet Table ──────────────────────────────────────────────────
function SpreadsheetTable({ columns, rows, totals }) {
  return (
    <div className="bg-gray-900/50 rounded-xl overflow-hidden border border-gray-800/50">
      <table className="w-full text-[11px]">
        <thead>
          <tr className="bg-gray-800/50">
            {columns.map((col, i) => (
              <th
                key={i}
                className={`px-3 py-2.5 font-medium text-gray-400 uppercase tracking-wider ${
                  col.align === 'right' ? 'text-right' : 'text-left'
                }`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-gray-800/20 transition-colors">
              {columns.map((col, j) => (
                <td
                  key={j}
                  className={`px-3 py-2 ${
                    col.align === 'right' ? 'text-right font-data text-gray-200' : 'text-gray-300'
                  } ${col.mono ? 'font-data' : ''}`}
                >
                  {row[col.key] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {totals && (
          <tfoot>
            <tr className="bg-gray-800/40 border-t border-gray-700">
              {columns.map((col, i) => (
                <td
                  key={i}
                  className={`px-3 py-2.5 font-semibold ${
                    col.align === 'right' ? 'text-right font-data text-gray-100' : 'text-gray-200'
                  }`}
                >
                  {totals[col.key] ?? ''}
                </td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

// ── Cost Stacked Bar ───────────────────────────────────────────────────
function CostStackedBar({ segments, total }) {
  return (
    <div className="space-y-3">
      <div className="h-8 rounded-lg overflow-hidden flex bg-gray-800/50">
        {segments.map((seg, i) => (
          <div
            key={i}
            className="h-full flex items-center justify-center text-[9px] font-semibold text-white/80 transition-all"
            style={{
              width: `${(seg.value / total) * 100}%`,
              backgroundColor: seg.color,
              minWidth: seg.value / total > 0.05 ? 'auto' : '2px',
            }}
            title={`${seg.name}: ${fmtR(seg.value)} (${((seg.value / total) * 100).toFixed(0)}%)`}
          >
            {seg.value / total > 0.12 && seg.name}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center gap-1.5 text-[10px] text-gray-400">
            <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: seg.color }} />
            <span>{seg.name}</span>
            <span className="font-data text-gray-300">{fmtR(seg.value)}</span>
            <span className="text-gray-600">({((seg.value / total) * 100).toFixed(0)}%)</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Profit Waterfall ───────────────────────────────────────────────────
function ProfitWaterfall({ revenue, cost, profit }) {
  const maxVal = Math.max(revenue, cost);
  const revW = (revenue / maxVal) * 100;
  const costW = (cost / maxVal) * 100;
  const profitPositive = profit >= 0;
  const profitW = Math.abs(profit) / maxVal * 100;

  return (
    <div className="space-y-3">
      {/* Revenue */}
      <div className="flex items-center gap-3">
        <span className="text-[11px] text-gray-400 w-16 text-right">Revenue</span>
        <div className="flex-1 h-7 bg-gray-800/50 rounded-md overflow-hidden">
          <div
            className="h-full rounded-md flex items-center px-2 text-[10px] font-data text-white/90 font-semibold"
            style={{ width: `${revW}%`, backgroundColor: '#22c55e' }}
          >
            {fmtR(revenue)}
          </div>
        </div>
      </div>
      {/* Cost */}
      <div className="flex items-center gap-3">
        <span className="text-[11px] text-gray-400 w-16 text-right">Costs</span>
        <div className="flex-1 h-7 bg-gray-800/50 rounded-md overflow-hidden">
          <div
            className="h-full rounded-md flex items-center px-2 text-[10px] font-data text-white/90 font-semibold"
            style={{ width: `${costW}%`, backgroundColor: '#ef4444' }}
          >
            {fmtR(cost)}
          </div>
        </div>
      </div>
      {/* Profit */}
      <div className="flex items-center gap-3">
        <span className="text-[11px] text-gray-400 w-16 text-right">Profit</span>
        <div className="flex-1 h-7 bg-gray-800/50 rounded-md overflow-hidden flex">
          {profitPositive ? (
            <>
              <div style={{ width: `${costW}%` }} />
              <div
                className="h-full rounded-md flex items-center px-2 text-[10px] font-data text-white/90 font-semibold"
                style={{ width: `${profitW}%`, backgroundColor: '#22c55e', minWidth: '60px' }}
              >
                {fmtR(profit)}
              </div>
            </>
          ) : (
            <div
              className="h-full rounded-md flex items-center px-2 text-[10px] font-data text-white/90 font-semibold"
              style={{ width: `${profitW}%`, backgroundColor: '#ef4444', minWidth: '60px' }}
            >
              {fmtR(profit)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Warning Card ───────────────────────────────────────────────────────
function WarningCard({ title, children }) {
  return (
    <div className="bg-amber-500/8 border border-amber-500/25 rounded-xl p-4 flex gap-3">
      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
      <div>
        {title && <div className="text-[11px] font-semibold text-amber-300 mb-1">{title}</div>}
        <div className="text-[11px] text-amber-200/80 leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────
export default function FinancialsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [property, setProperty] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      getProperty(id),
      getDevelopmentPotential(id),
    ])
      .then(([prop, devPot]) => {
        setProperty(prop);
        setData(devPot);
      })
      .catch(err => setError(err.response?.data?.detail || 'Failed to load financial data'))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-950">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-ocean-400 animate-spin" />
          <p className="text-sm text-gray-500">Loading financial analysis...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-950">
        <div className="flex flex-col items-center gap-3 max-w-md text-center">
          <XCircle className="w-8 h-8 text-red-400" />
          <p className="text-sm text-red-400">{error}</p>
          <button onClick={() => navigate(-1)} className="text-xs text-ocean-400 hover:text-ocean-300 mt-2">
            Go back
          </button>
        </div>
      </div>
    );
  }

  if (!data?.financials) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-950">
        <div className="flex flex-col items-center gap-3">
          <DollarSign className="w-8 h-8 text-gray-700" />
          <p className="text-sm text-gray-500">No financial data available for this property.</p>
          <button onClick={() => navigate(-1)} className="text-xs text-ocean-400 hover:text-ocean-300 mt-2">
            Go back
          </button>
        </div>
      </div>
    );
  }

  const f = data.financials;
  const y = data.yield || {};
  const um = data.unit_mix || [];
  const p = data.parking || {};
  const z = data.zoning || {};
  const s = data.site || {};
  const d = data.density || {};
  const suburb = (data.suburb || property?.suburb || '').toUpperCase();
  const mc = marginColor(f.margin_pct);
  const isLuxury = LUXURY_SUBURBS.includes(suburb);
  const totalUnits = y.estimated_units || 1;

  // Cost breakdown segments
  const costSegments = [
    { name: 'Construction', value: f.construction_cost, color: '#3b98f5' },
    { name: 'Prof. Fees', value: f.professional_fees, color: '#a855f7' },
    { name: 'Contingency', value: f.contingency, color: '#f59e0b' },
  ];
  const basementCost = f.total_development_cost - f.construction_cost - f.professional_fees - f.contingency;
  if (basementCost > 0 && p.recommended_solution === 'basement') {
    costSegments.push({ name: 'Basement Parking', value: Math.round(basementCost), color: '#6b7280' });
  }

  // Cost table
  const costRows = [
    { item: 'Construction', amount: fmtR(f.construction_cost), pctTotal: pct((f.construction_cost / f.total_development_cost) * 100), rate: `${fmtRFull(f.construction_cost_per_sqm)}/m²` },
    { item: 'Professional Fees', amount: fmtR(f.professional_fees), pctTotal: pct((f.professional_fees / f.total_development_cost) * 100), rate: '12% of construction' },
    { item: 'Contingency', amount: fmtR(f.contingency), pctTotal: pct((f.contingency / f.total_development_cost) * 100), rate: '10% of construction' },
  ];
  if (basementCost > 0 && p.recommended_solution === 'basement') {
    costRows.push({ item: 'Basement Parking', amount: fmtR(basementCost), pctTotal: pct((basementCost / f.total_development_cost) * 100), rate: `R 6,500/m² × ${p.basement_area_sqm?.toLocaleString() || '—'}m²` });
  }

  // Revenue table from unit_mix
  const revenueRows = um.filter(u => u.count > 0).map(u => ({
    type: u.label,
    count: u.count,
    size: `${u.size_sqm}`,
    totalSqm: (u.count * u.size_sqm).toLocaleString(),
    rate: fmtRFull(u.revenue_per_unit ? Math.round(u.revenue_per_unit / u.size_sqm) : 0),
    revenue: fmtR(u.total_revenue),
  }));

  // Revenue chart data
  const revenueChartData = um.filter(u => u.count > 0).map(u => ({
    name: u.label,
    revenue: u.total_revenue,
    count: u.count,
    size: u.size_sqm,
    color: UNIT_TYPE_COLORS[u.type] || '#3b98f5',
  }));

  // Breakeven
  const breakeven = y.net_sellable_sqm > 0 ? Math.round(f.total_development_cost / y.net_sellable_sqm) : 0;

  // Market value lookup (derive from unit_mix data)
  const marketValues = um.filter(u => u.count > 0).map(u => ({
    type: u.label,
    rate: fmtRFull(u.revenue_per_unit ? Math.round(u.revenue_per_unit / u.size_sqm) : 0),
  }));

  // Warnings
  const warnings = [];
  if (isLuxury) {
    warnings.push({
      title: `${data.suburb || property?.suburb} is a premium area`,
      message: `This model uses generic Cape Town construction rates (${fmtRFull(f.construction_cost_per_sqm)}/m²). Premium suburbs typically see R 20,000–75,000/m² construction costs and significantly higher market values than modelled.`,
    });
  }
  if (f.margin_pct < -20) {
    warnings.push({
      title: 'Deeply negative margin',
      message: `A ${f.margin_pct}% margin strongly suggests the generic cost and revenue assumptions do not fit this property or area. The actual financials could be significantly different.`,
    });
  }
  warnings.push({
    title: 'Costs not included in this model',
    message: 'Land acquisition, financing costs (interest), marketing & sales (2–4%), holding costs during construction, site remediation/demolition, municipal contributions, and transfer duties.',
  });

  const propertyLabel = property?.full_address || `ERF ${data.erf_number}, ${data.suburb}`;

  return (
    <div className="h-full overflow-y-auto bg-gray-950">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 space-y-5">

        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="flex items-start gap-3">
          <button
            onClick={() => navigate(-1)}
            className="mt-1 w-8 h-8 rounded-lg bg-gray-800 border border-gray-700 flex items-center justify-center hover:bg-gray-700 transition-colors shrink-0"
          >
            <ArrowLeft className="w-4 h-4 text-gray-300" />
          </button>
          <div>
            <h1 className="text-lg font-bold text-white">{propertyLabel}</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-gray-500">Zoning: {z.code || '—'}</span>
              <span className="text-gray-700">·</span>
              <span className="text-xs text-gray-500">{y.development_type?.replace(/_/g, ' ') || '—'}</span>
              <span className="text-gray-700">·</span>
              <span className="text-xs text-gray-500">{s.total_area_sqm?.toLocaleString() || '—'} m²</span>
            </div>
          </div>
        </div>

        {/* ── Viability Banner ────────────────────────────────────── */}
        <div className={`${mc.bg} border ${mc.border} rounded-2xl p-5 flex items-center justify-between`}>
          <div className="flex items-center gap-3">
            {f.viable ? (
              <CheckCircle2 className="w-8 h-8 text-green-400" />
            ) : (
              <XCircle className="w-8 h-8 text-red-400" />
            )}
            <div>
              <div className={`text-lg font-bold ${mc.text}`}>
                {f.viable ? 'VIABLE' : 'NOT VIABLE'}
              </div>
              <div className="text-[11px] text-gray-400">
                {f.viable ? 'Margin exceeds 15% threshold' : 'Margin below 15% viability threshold'}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className={`text-2xl font-bold font-data ${mc.text}`}>{f.margin_pct}%</div>
            <div className="text-[10px] text-gray-500 uppercase tracking-wider">Margin</div>
          </div>
        </div>

        {/* ── Key Metrics ─────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <MetricCard label="Total Dev Cost" value={fmtR(f.total_development_cost)} sub={`${fmtRFull(y.max_gfa_sqm ? Math.round(f.total_development_cost / y.max_gfa_sqm) : 0)}/m² GFA`} />
          <MetricCard label="Est. Revenue" value={fmtR(f.estimated_revenue)} color="text-green-400" sub={`${fmtRFull(y.net_sellable_sqm ? Math.round(f.estimated_revenue / y.net_sellable_sqm) : 0)}/m² sellable`} />
          <MetricCard
            label="Est. Profit"
            value={fmtR(f.estimated_profit)}
            color={f.estimated_profit >= 0 ? 'text-green-400' : 'text-red-400'}
            sub={`${fmtR(Math.round(f.estimated_profit / totalUnits))}/unit`}
          />
          <MetricCard label="ROI" value={`${f.roi_pct}%`} color={mc.text} sub={`Breakeven: ${fmtRFull(breakeven)}/m²`} />
        </div>

        {/* ── Cost Breakdown ──────────────────────────────────────── */}
        <Section title="Cost Breakdown" icon={DollarSign}>
          <CostStackedBar segments={costSegments} total={f.total_development_cost} />

          <div className="mt-4">
            <SpreadsheetTable
              columns={[
                { key: 'item', label: 'Item' },
                { key: 'amount', label: 'Amount', align: 'right' },
                { key: 'pctTotal', label: '% of Total', align: 'right' },
                { key: 'rate', label: 'Rate / Basis', align: 'right' },
              ]}
              rows={costRows}
              totals={{ item: 'Total Development Cost', amount: fmtR(f.total_development_cost), pctTotal: '100%', rate: '' }}
            />
          </div>

          <Formula>
            Total Dev Cost = (GFA × R/m²) + 12% Prof Fees + 10% Contingency{p.recommended_solution === 'basement' ? ' + Basement Parking' : ''}
          </Formula>
        </Section>

        {/* ── Revenue Breakdown ───────────────────────────────────── */}
        <Section title="Revenue Breakdown" icon={TrendingUp}>
          {revenueChartData.length > 0 && (
            <div className="mb-4">
              <RevenueBarChart data={revenueChartData} />
            </div>
          )}

          <SpreadsheetTable
            columns={[
              { key: 'type', label: 'Unit Type' },
              { key: 'count', label: 'Units', align: 'right', mono: true },
              { key: 'size', label: 'Size (m²)', align: 'right', mono: true },
              { key: 'totalSqm', label: 'Total m²', align: 'right', mono: true },
              { key: 'rate', label: 'Rate (R/m²)', align: 'right' },
              { key: 'revenue', label: 'Revenue', align: 'right' },
            ]}
            rows={revenueRows}
            totals={{
              type: 'Total',
              count: totalUnits,
              size: '',
              totalSqm: y.net_sellable_sqm?.toLocaleString() || '—',
              rate: '',
              revenue: fmtR(f.estimated_revenue),
            }}
          />

          <Formula>
            Revenue = Σ(Unit Count × Unit Size × Market Rate/m²)
          </Formula>
        </Section>

        {/* ── Profit Analysis ─────────────────────────────────────── */}
        <Section title="Profit Analysis" icon={TrendingUp}>
          <ProfitWaterfall revenue={f.estimated_revenue} cost={f.total_development_cost} profit={f.estimated_profit} />

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
            <div className="bg-gray-800/40 rounded-lg p-3">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">Profit</div>
              <div className={`text-sm font-bold font-data ${f.estimated_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {fmtR(f.estimated_profit)}
              </div>
            </div>
            <div className="bg-gray-800/40 rounded-lg p-3">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">Margin</div>
              <div className={`text-sm font-bold font-data ${mc.text}`}>{f.margin_pct}%</div>
            </div>
            <div className="bg-gray-800/40 rounded-lg p-3">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">ROI</div>
              <div className={`text-sm font-bold font-data ${mc.text}`}>{f.roi_pct}%</div>
            </div>
            <div className="bg-gray-800/40 rounded-lg p-3">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">Breakeven</div>
              <div className="text-sm font-bold font-data text-gray-200">{fmtRFull(breakeven)}/m²</div>
            </div>
          </div>

          <Formula>
            Profit = Revenue − Dev Cost &nbsp;|&nbsp; Margin = Profit ÷ Dev Cost × 100 &nbsp;|&nbsp; Breakeven = Dev Cost ÷ Net Sellable m²
          </Formula>
        </Section>

        {/* ── Unit Economics ──────────────────────────────────────── */}
        <Section title="Unit Economics" icon={Building2}>
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
            <MetricCard label="Cost / Unit" value={fmtR(Math.round(f.total_development_cost / totalUnits))} />
            <MetricCard label="Revenue / Unit" value={fmtR(Math.round(f.estimated_revenue / totalUnits))} color="text-green-400" />
            <MetricCard
              label="Profit / Unit"
              value={fmtR(Math.round(f.estimated_profit / totalUnits))}
              color={f.estimated_profit >= 0 ? 'text-green-400' : 'text-red-400'}
            />
            <MetricCard label="Cost / m² (GFA)" value={fmtRFull(y.max_gfa_sqm ? Math.round(f.total_development_cost / y.max_gfa_sqm) : 0)} />
            <MetricCard label="Revenue / m² (sell)" value={fmtRFull(y.net_sellable_sqm ? Math.round(f.estimated_revenue / y.net_sellable_sqm) : 0)} color="text-green-400" />
          </div>
        </Section>

        {/* ── Development Parameters ──────────────────────────────── */}
        <Section title="Development Parameters" icon={Info}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Site */}
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Site</div>
              <div className="space-y-1 text-[11px]">
                <Row label="Total area" value={`${s.total_area_sqm?.toLocaleString()} m²`} />
                <Row label="Buildable area" value={`${s.buildable_area_sqm?.toLocaleString()} m²`} />
                <Row label="Utilization" value={pct(s.site_utilization_pct)} />
                <Row label="Urban edge" value={s.inside_urban_edge ? 'Inside' : 'Outside'} />
              </div>
            </div>

            {/* Zoning */}
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Zoning ({z.code})</div>
              <div className="space-y-1 text-[11px]">
                <Row label="Coverage" value={z.rules?.coverage ? `${z.rules.coverage}%` : '—'} />
                <Row label="FAR" value={z.rules?.far ?? '—'} />
                <Row label="Max height" value={z.rules?.height ? `${z.rules.height}m` : '—'} />
                <Row label="Max floors" value={z.rules?.max_floors ?? '—'} />
              </div>
            </div>

            {/* Yield */}
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Yield</div>
              <div className="space-y-1 text-[11px]">
                <Row label="Gross Floor Area" value={`${y.max_gfa_sqm?.toLocaleString()} m²`} />
                <Row label="Net sellable" value={`${y.net_sellable_sqm?.toLocaleString()} m²`} />
                <Row label="Floor efficiency" value={pct(y.floor_efficiency_pct)} />
                <Row label="Units" value={y.estimated_units} />
                <Row label="Bedrooms" value={y.total_bedrooms} />
              </div>
            </div>

            {/* Parking */}
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Parking</div>
              <div className="space-y-1 text-[11px]">
                <Row label="Total bays" value={p.total_bays} />
                <Row label="Resident" value={p.resident_bays} />
                <Row label="Visitor" value={p.visitor_bays} />
                <Row label="Solution" value={p.recommended_solution} />
                <Row label="Area" value={`${(p.recommended_solution === 'basement' ? p.basement_area_sqm : p.surface_area_sqm)?.toLocaleString()} m²`} />
              </div>
            </div>

            {/* Density */}
            <div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Density</div>
              <div className="space-y-1 text-[11px]">
                <Row label="Units/ha" value={d.units_per_ha} />
                <Row label="Beds/ha" value={d.beds_per_ha} />
                <Row label="FAR utilization" value={pct(d.far_utilization_pct)} />
                <Row label="Coverage utilization" value={pct(d.coverage_utilization_pct)} />
              </div>
            </div>
          </div>
        </Section>

        {/* ── Assumptions & Warnings ──────────────────────────────── */}
        <Section title="Assumptions & Warnings" icon={AlertTriangle}>
          <div className="space-y-4">
            {/* Warnings */}
            {warnings.map((w, i) => (
              <WarningCard key={i} title={w.title}>{w.message}</WarningCard>
            ))}

            {/* Assumptions table */}
            <div className="mt-2">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Key Assumptions</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-[11px]">
                <Row label="Construction rate" value={`${fmtRFull(f.construction_cost_per_sqm)}/m²`} />
                <Row label="Floor efficiency" value={pct(y.floor_efficiency_pct)} />
                <Row label="Professional fees" value="12% of construction" />
                <Row label="Contingency" value="10% of construction" />
                <Row label="Parking ratio" value={z.rules?.parking_ratio ? `${z.rules.parking_ratio} bays/unit` : '—'} />
                <Row label="Development type" value={y.development_type?.replace(/_/g, ' ')} />
              </div>
            </div>

            {/* Market values */}
            {marketValues.length > 0 && (
              <div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Market Values Used</div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-1 text-[11px]">
                  {marketValues.map((mv, i) => (
                    <Row key={i} label={mv.type} value={`${mv.rate}/m²`} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </Section>

        {/* ── Disclaimer ──────────────────────────────────────────── */}
        <div className="text-[10px] text-gray-600 text-center pb-6 leading-relaxed">
          Screening-level estimate based on CTZS Table A zoning rules. Actual development rights may differ
          based on overlay zones, Scheme amendments, and Council discretion. Not intended as financial advice.
        </div>

      </div>
    </div>
  );
}

// Simple label-value row
function Row({ label, value }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="font-data text-gray-300">{value}</span>
    </div>
  );
}
