import { useMemo, useState } from 'react';
import { MOCK_SITE } from '@/mock/site';
import { useSensorStore } from '@/store/sensorStore';
import { useAIStore } from '@/store/aiStore';
import { fmtAgo, fmtNum } from '@/utils/format';
import { clsx } from '@/utils/clsx';

/**
 * Nimba Site Map.
 *
 * A canvas-free, Leaflet-free, offline-first operator map:
 * - Background is the pre-rendered Copernicus GLO-30 hillshade at
 *   /dem/nimba-hillshade.png (same geography as the 3D twin).
 * - Nodes + site boundary + slope polygons are overlaid as SVG so the
 *   geo-to-pixel math is explicit and the result pixel-matches between
 *   the dashboard, PDF exports, and the twin.
 *
 * Lat/lng are mapped linearly across the 20 km x 20 km hillshade bounds
 * (acceptable for a ~22 km x 22 km tile at this latitude — a Mercator
 * correction over this extent is sub-pixel).
 */

const BOUNDS = {
  minLat: 7.5,
  maxLat: 7.7,
  minLng: -8.6,
  maxLng: -8.4,
};

const NODE_COLORS = {
  ONLINE: '#10B981',
  DEGRADED: '#F59E0B',
  OFFLINE: '#EF4444',
} as const;

function riskColor(score: number): string {
  if (score >= 0.7) return '#EF4444';
  if (score >= 0.4) return '#F59E0B';
  if (score >= 0.2) return '#FACC15';
  return '#10B981';
}

function latLngToPct(lat: number, lng: number): { xPct: number; yPct: number } {
  const xPct = ((lng - BOUNDS.minLng) / (BOUNDS.maxLng - BOUNDS.minLng)) * 100;
  // Latitude: higher lat is further north → lower y in CSS coords.
  const yPct = (1 - (lat - BOUNDS.minLat) / (BOUNDS.maxLat - BOUNDS.minLat)) * 100;
  return { xPct, yPct };
}

export function SiteMap({ height = 360 }: { height?: number }) {
  const env = useSensorStore((s) => s.latestEnvReadings);
  const slopes = useAIStore((s) => s.slopeWatchPredictions);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  const boundaryPoints = useMemo(
    () =>
      MOCK_SITE.boundary.coordinates[0]
        .map(([lng, lat]) => {
          const { xPct, yPct } = latLngToPct(lat, lng);
          return `${xPct.toFixed(3)}%,${yPct.toFixed(3)}%`;
        })
        .join(' '),
    [],
  );

  const hoverNode = hoveredNode ? MOCK_SITE.nodes.find((n) => n.id === hoveredNode) : null;
  const hoverReading = hoverNode ? env[hoverNode.id] : null;

  return (
    <div
      className="relative overflow-hidden rounded-xl border border-bg-line bg-[#1A1F2E]"
      style={{
        height,
        backgroundImage: "url(/dem/nimba-hillshade.png)",
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {/* Overlay for site boundary, slopes, and nodes — svg so coordinates
          are declarative percentages aligned to the hillshade. */}
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
      >
        {/* Site concession boundary */}
        <polygon
          points={boundaryPoints}
          fill="rgba(34, 211, 238, 0.08)"
          stroke="#22D3EE"
          strokeWidth="0.18"
          vectorEffect="non-scaling-stroke"
        />
        {/* Slope polygons (risk-coloured) */}
        {MOCK_SITE.slopes.map((slope) => {
          const risk = slopes[slope.id]?.risk_score ?? 0.1;
          const pts = slope.geometry.coordinates[0]
            .map(([lng, lat]) => {
              const { xPct, yPct } = latLngToPct(lat, lng);
              return `${xPct.toFixed(3)},${yPct.toFixed(3)}`;
            })
            .join(' ');
          return (
            <polygon
              key={slope.id}
              points={pts}
              fill={riskColor(risk)}
              fillOpacity={0.35}
              stroke={riskColor(risk)}
              strokeWidth="0.2"
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
      </svg>

      {/* Sensor node markers — divs so they can carry labels / tooltips. */}
      {MOCK_SITE.nodes.map((node) => {
        const { xPct, yPct } = latLngToPct(node.lat, node.lng);
        const color = NODE_COLORS[node.status] ?? '#94A3B8';
        return (
          <button
            key={node.id}
            type="button"
            onMouseEnter={() => setHoveredNode(node.id)}
            onMouseLeave={() => setHoveredNode(null)}
            onFocus={() => setHoveredNode(node.id)}
            onBlur={() => setHoveredNode(null)}
            className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center"
            style={{ left: `${xPct}%`, top: `${yPct}%` }}
            title={node.name}
          >
            <span
              className="block h-3 w-3 rounded-full ring-2 ring-bg-deep"
              style={{ background: color, boxShadow: `0 0 0 2px ${color}55` }}
            />
            <span
              className={clsx(
                'mt-1 rounded bg-bg-deep/90 px-1.5 py-0.5 font-mono text-[9px] text-slate-200 ring-1 ring-bg-line',
                hoveredNode === node.id ? 'opacity-100' : 'opacity-80',
              )}
            >
              {node.id}
            </span>
          </button>
        );
      })}

      {/* Hover tooltip panel — one shared panel to avoid z-index churn. */}
      {hoverNode && (
        <div className="absolute left-2 top-2 w-60 rounded bg-bg-deep/95 p-2 text-[11px] text-slate-100 shadow-lg ring-1 ring-bg-line">
          <div className="text-xs font-semibold">{hoverNode.name}</div>
          <div className="text-[10px] uppercase tracking-wider text-slate-400">
            {hoverNode.node_type} &middot; {hoverNode.status}
          </div>
          {hoverReading?.ph != null && (
            <div className="mt-1 text-slate-300">
              pH <b>{fmtNum(hoverReading.ph, 2)}</b> &middot; Turb{' '}
              <b>{fmtNum(hoverReading.turbidity, 1)}</b> NTU
            </div>
          )}
          {hoverReading && (
            <div className="text-[10px] text-slate-500">{fmtAgo(hoverReading.timestamp)}</div>
          )}
        </div>
      )}

      {/* Compass + scale legend */}
      <div className="pointer-events-none absolute right-2 top-2 flex items-center gap-2 rounded bg-bg-deep/80 px-2 py-1 text-[10px] text-slate-300 ring-1 ring-bg-line">
        <span className="font-mono">N &uarr;</span>
        <span>&middot;</span>
        <span>&asymp; 22 km across</span>
      </div>

      <div className="pointer-events-none absolute bottom-1 right-1 rounded bg-bg-deep/80 px-2 py-0.5 text-[10px] text-slate-400 ring-1 ring-bg-line">
        Terrain: Copernicus GLO-30 (ESA) &middot; offline-rendered
      </div>
    </div>
  );
}
