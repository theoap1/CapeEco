/**
 * SiteBoundaryDiagram — renders a property polygon as an SVG with dimensioned side lengths.
 *
 * Props:
 *   geometry   — GeoJSON geometry object ({ type: "Polygon", coordinates: [...] })
 *   areaSqm    — total area in m²
 *   setbacks   — optional { front, side, rear } in meters (draws dashed inset)
 *   width      — SVG width (default 680)
 *   height     — SVG height (default 480)
 */

// ── Haversine distance (meters) between two EPSG:4326 points ────────
function haversine(lat1, lon1, lat2, lon2) {
  const R = 6371000; // Earth radius in meters
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ── Project lat/lon ring → SVG pixel coordinates ────────────────────
function projectToSVG(ring, width, height, padding = 60) {
  // ring = [[lon, lat], ...] (GeoJSON order)
  const lons = ring.map((c) => c[0]);
  const lats = ring.map((c) => c[1]);

  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);

  const bboxW = maxLon - minLon || 1e-6;
  const bboxH = maxLat - minLat || 1e-6;

  const drawW = width - padding * 2;
  const drawH = height - padding * 2;

  // Maintain aspect ratio using cos correction for latitude
  const midLat = (minLat + maxLat) / 2;
  const cosLat = Math.cos((midLat * Math.PI) / 180);

  const scaleX = drawW / (bboxW * cosLat);
  const scaleY = drawH / bboxH;
  const scale = Math.min(scaleX, scaleY);

  // Center the polygon in the SVG
  const projW = bboxW * cosLat * scale;
  const projH = bboxH * scale;
  const offsetX = padding + (drawW - projW) / 2;
  const offsetY = padding + (drawH - projH) / 2;

  return ring.map(([lon, lat]) => ({
    x: offsetX + (lon - minLon) * cosLat * scale,
    y: offsetY + (maxLat - lat) * scale, // flip Y
    lon,
    lat,
  }));
}

// ── Format distance label ───────────────────────────────────────────
function fmtDist(m) {
  if (m >= 100) return `${m.toFixed(1)}m`;
  if (m >= 10) return `${m.toFixed(2)}m`;
  return `${m.toFixed(2)}m`;
}

export default function SiteBoundaryDiagram({
  geometry,
  areaSqm,
  setbacks,
  width = 680,
  height = 480,
}) {
  if (!geometry?.coordinates?.[0]) return null;

  const ring = geometry.coordinates[0];
  // Remove closing duplicate (last coord == first)
  const coords =
    ring.length > 1 &&
    ring[0][0] === ring[ring.length - 1][0] &&
    ring[0][1] === ring[ring.length - 1][1]
      ? ring.slice(0, -1)
      : ring;

  const points = projectToSVG(coords, width, height);

  // Build polygon path
  const polyPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ') + ' Z';

  // Calculate side lengths + label positions
  const sides = [];
  for (let i = 0; i < points.length; i++) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    const dist = haversine(a.lat, a.lon, b.lat, b.lon);

    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const angle = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;

    // Offset label slightly away from edge
    const nx = -(b.y - a.y);
    const ny = b.x - a.x;
    const len = Math.sqrt(nx * nx + ny * ny) || 1;
    const offsetDist = 14;

    sides.push({
      dist,
      label: fmtDist(dist),
      mx: mx + (nx / len) * offsetDist,
      my: my + (ny / len) * offsetDist,
      angle: angle > 90 || angle < -90 ? angle + 180 : angle,
    });
  }

  // Corner markers
  const corners = points.map((p, i) => ({
    x: p.x,
    y: p.y,
    label: String.fromCharCode(65 + i), // A, B, C, ...
  }));

  // Perimeter
  const perimeter = sides.reduce((s, side) => s + side.dist, 0);

  // North arrow position (top-right)
  const arrowX = width - 40;
  const arrowY = 35;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height="auto"
      className="border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900"
      style={{ maxHeight: `${height}px` }}
    >
      {/* Background grid */}
      <defs>
        <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e5e7eb" strokeWidth="0.3" className="dark:stroke-gray-800" />
        </pattern>
      </defs>
      <rect width={width} height={height} fill="url(#grid)" rx="8" />

      {/* Property boundary polygon */}
      <path
        d={polyPath}
        fill="rgba(59, 152, 245, 0.08)"
        stroke="#3b98f5"
        strokeWidth="2.5"
        strokeLinejoin="round"
      />

      {/* Setback inset (dashed) */}
      {setbacks && (
        <path
          d={polyPath}
          fill="none"
          stroke="#f97316"
          strokeWidth="1.2"
          strokeDasharray="6 4"
          transform={`scale(0.9) translate(${width * 0.05}, ${height * 0.05})`}
          opacity="0.5"
        />
      )}

      {/* Side dimension lines + labels */}
      {sides.map((side, i) => {
        const a = points[i];
        const b = points[(i + 1) % points.length];
        return (
          <g key={i}>
            {/* Dimension line ticks at endpoints */}
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#94a3b8" strokeWidth="0.5" strokeDasharray="3 2" />
            {/* Label */}
            <text
              x={side.mx}
              y={side.my}
              textAnchor="middle"
              dominantBaseline="middle"
              transform={`rotate(${side.angle}, ${side.mx}, ${side.my})`}
              fill="#1e40af"
              fontSize="11"
              fontFamily="'JetBrains Mono', monospace"
              fontWeight="600"
            >
              {side.label}
            </text>
          </g>
        );
      })}

      {/* Corner markers */}
      {corners.map((c) => (
        <g key={c.label}>
          <circle cx={c.x} cy={c.y} r="4" fill="#3b98f5" stroke="white" strokeWidth="1.5" />
          <text
            x={c.x}
            y={c.y - 10}
            textAnchor="middle"
            fill="#3b98f5"
            fontSize="10"
            fontWeight="700"
            fontFamily="'DM Sans', sans-serif"
          >
            {c.label}
          </text>
        </g>
      ))}

      {/* North arrow */}
      <g transform={`translate(${arrowX}, ${arrowY})`}>
        <polygon points="0,-18 -6,0 6,0" fill="#374151" />
        <text y="14" textAnchor="middle" fill="#374151" fontSize="11" fontWeight="700" fontFamily="'DM Sans', sans-serif">
          N
        </text>
      </g>

      {/* Area + perimeter info box */}
      <g transform={`translate(12, ${height - 50})`}>
        <rect width="220" height="40" rx="6" fill="white" stroke="#e5e7eb" strokeWidth="1" opacity="0.95" />
        <text x="10" y="16" fill="#374151" fontSize="11" fontFamily="'JetBrains Mono', monospace" fontWeight="600">
          Area: {areaSqm ? `${Math.round(areaSqm).toLocaleString()} m²` : '—'}
          {areaSqm ? ` (${(areaSqm / 10000).toFixed(4)} ha)` : ''}
        </text>
        <text x="10" y="32" fill="#6b7280" fontSize="10" fontFamily="'JetBrains Mono', monospace">
          Perimeter: {fmtDist(perimeter)}
        </text>
      </g>
    </svg>
  );
}
