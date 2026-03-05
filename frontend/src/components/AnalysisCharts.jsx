import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts';

const CHART_COLORS = {
  ocean: '#3b98f5',
  green: '#22c55e',
  amber: '#f59e0b',
  red: '#ef4444',
  purple: '#a855f7',
};

const RISK_BAR_COLORS = ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444'];

// Custom dark tooltip
function DarkTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 shadow-xl">
      <p className="text-[11px] text-gray-400 mb-0.5">{label}</p>
      <p className="text-sm font-bold text-white font-data">{payload[0].value}</p>
    </div>
  );
}

/**
 * Green Star radar chart — shows 5 sustainability categories
 * data: [{ category: 'Energy', score: 18, max: 25 }, ...]
 */
export function GreenStarRadar({ data }) {
  if (!data?.length) return null;

  const chartData = data.map(d => ({
    category: d.category,
    score: d.score,
    fullMark: d.max,
  }));

  return (
    <div className="w-full h-48">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={chartData} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="rgb(55 65 81 / 0.4)" />
          <PolarAngleAxis
            dataKey="category"
            tick={{ fill: '#9ca3af', fontSize: 10, fontFamily: 'DM Sans' }}
          />
          <Radar
            name="Score"
            dataKey="score"
            stroke={CHART_COLORS.ocean}
            fill={CHART_COLORS.ocean}
            fillOpacity={0.2}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Crime categories bar chart — top N categories
 * data: [{ category: 'Burglary', count: 245 }, ...]
 */
export function CrimeBarChart({ data, maxItems = 6 }) {
  if (!data?.length) return null;

  const chartData = data
    .slice(0, maxItems)
    .map(d => ({
      name: d.category?.length > 18 ? d.category.slice(0, 16) + '…' : d.category,
      value: d.count || d.weighted_score || 0,
    }));

  const maxVal = Math.max(...chartData.map(d => d.value));

  return (
    <div className="w-full h-44">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 8, top: 4, bottom: 4 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={110}
            tick={{ fill: '#9ca3af', fontSize: 10, fontFamily: 'DM Sans' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<DarkTooltip />} cursor={{ fill: 'rgb(55 65 81 / 0.2)' }} />
          <Bar dataKey="value" radius={[0, 3, 3, 0]} maxBarSize={14}>
            {chartData.map((entry, i) => (
              <Cell
                key={i}
                fill={RISK_BAR_COLORS[Math.min(Math.floor((entry.value / maxVal) * 4), 4)]}
                fillOpacity={0.8}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Load shedding stage impact chart — stages 1-8
 * data: [{ stage: 1, hours: 2.5 }, { stage: 2, hours: 4 }, ...]
 */
export function StageImpactChart({ data }) {
  if (!data?.length) return null;

  const STAGE_COLORS_HEX = [
    '#fef08a', '#fde047', '#facc15', '#f59e0b',
    '#f97316', '#ef4444', '#dc2626', '#991b1b',
  ];

  const chartData = data.map(d => ({
    name: `S${d.stage}`,
    hours: d.hours_per_day || d.hours || 0,
  }));

  return (
    <div className="w-full h-36">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ left: -20, right: 4, top: 4, bottom: 4 }}>
          <XAxis
            dataKey="name"
            tick={{ fill: '#9ca3af', fontSize: 9, fontFamily: 'JetBrains Mono' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#6b7280', fontSize: 9, fontFamily: 'JetBrains Mono' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<DarkTooltip />} cursor={{ fill: 'rgb(55 65 81 / 0.2)' }} />
          <Bar dataKey="hours" radius={[3, 3, 0, 0]} maxBarSize={24}>
            {chartData.map((_, i) => (
              <Cell key={i} fill={STAGE_COLORS_HEX[i]} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Revenue by unit type — vertical bar chart for financials page
 * data: [{ name: 'Studio', revenue: 4800000, count: 5, size: 30, color: '#a78bfa' }, ...]
 */
export function RevenueBarChart({ data }) {
  if (!data?.length) return null;

  function RevenueTooltip({ active, payload }) {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    const revM = (d.revenue / 1e6).toFixed(1);
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 shadow-xl">
        <p className="text-[11px] text-gray-400 mb-0.5">{d.name}</p>
        <p className="text-sm font-bold text-white font-data">R {revM}M</p>
        <p className="text-[10px] text-gray-500">{d.count}× {d.size}m²</p>
      </div>
    );
  }

  return (
    <div className="w-full h-48">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ left: -10, right: 4, top: 4, bottom: 4 }}>
          <XAxis
            dataKey="name"
            tick={{ fill: '#9ca3af', fontSize: 9, fontFamily: 'DM Sans' }}
            axisLine={false}
            tickLine={false}
            interval={0}
            angle={-25}
            textAnchor="end"
            height={50}
          />
          <YAxis
            tick={{ fill: '#6b7280', fontSize: 9, fontFamily: 'JetBrains Mono' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={v => `R${(v / 1e6).toFixed(0)}M`}
          />
          <Tooltip content={<RevenueTooltip />} cursor={{ fill: 'rgb(55 65 81 / 0.2)' }} />
          <Bar dataKey="revenue" radius={[4, 4, 0, 0]} maxBarSize={40}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color || CHART_COLORS.ocean} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Municipal health score gauge — a horizontal gauge with colored segments
 * score: number 0-100
 */
export function HealthGauge({ score, label = 'Health Score' }) {
  if (score == null) return null;

  const color = score >= 70 ? CHART_COLORS.green
    : score >= 50 ? CHART_COLORS.amber
    : CHART_COLORS.red;

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-[11px] text-gray-500 uppercase tracking-wider font-data">{label}</span>
        <span className="text-2xl font-bold font-data" style={{ color }}>{score}</span>
      </div>
      <div className="gauge-track">
        <div className="gauge-fill" style={{ width: `${score}%`, background: color }} />
      </div>
    </div>
  );
}
