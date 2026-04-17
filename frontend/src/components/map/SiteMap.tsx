import { CircleMarker, MapContainer, Polygon, Popup, TileLayer } from 'react-leaflet';
import { useMemo } from 'react';
import type { LatLngExpression } from 'leaflet';
import { MOCK_SITE } from '@/mock/site';
import { useSensorStore } from '@/store/sensorStore';
import { useAIStore } from '@/store/aiStore';
import { fmtAgo, fmtNum } from '@/utils/format';

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

export function SiteMap({ height = 360 }: { height?: number }) {
  const env = useSensorStore((s) => s.latestEnvReadings);
  const slopes = useAIStore((s) => s.slopeWatchPredictions);

  const center = useMemo<LatLngExpression>(
    () => [MOCK_SITE.centroid.lat, MOCK_SITE.centroid.lng],
    [],
  );

  const boundary: LatLngExpression[] = MOCK_SITE.boundary.coordinates[0].map(([lng, lat]) => [
    lat,
    lng,
  ]);

  return (
    <div className="overflow-hidden rounded-xl border border-bg-line" style={{ height }}>
      <MapContainer center={center} zoom={14} style={{ height: '100%', width: '100%' }} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Polygon positions={boundary} pathOptions={{ color: '#22D3EE', weight: 1.2, fillOpacity: 0.05 }} />
        {MOCK_SITE.slopes.map((slope) => {
          const ring: LatLngExpression[] = slope.geometry.coordinates[0].map(([lng, lat]) => [
            lat,
            lng,
          ]);
          const risk = slopes[slope.id]?.risk_score ?? 0.1;
          return (
            <Polygon
              key={slope.id}
              positions={ring}
              pathOptions={{
                color: riskColor(risk),
                fillColor: riskColor(risk),
                fillOpacity: 0.35,
                weight: 1.4,
              }}
            >
              <Popup>
                <div className="text-xs">
                  <div className="font-semibold">{slope.name}</div>
                  <div>Risk: {Math.round(risk * 100)}%</div>
                  <div>Tier: {slopes[slope.id]?.alert_tier ?? 'NORMAL'}</div>
                </div>
              </Popup>
            </Polygon>
          );
        })}
        {MOCK_SITE.nodes.map((node) => {
          const reading = env[node.id];
          return (
            <CircleMarker
              key={node.id}
              center={[node.lat, node.lng]}
              radius={7}
              pathOptions={{
                color: NODE_COLORS[node.status],
                fillColor: NODE_COLORS[node.status],
                fillOpacity: 0.75,
                weight: 2,
              }}
            >
              <Popup>
                <div className="text-xs">
                  <div className="font-semibold">{node.name}</div>
                  <div>{node.node_type} · {node.status}</div>
                  {reading?.ph != null && <div>pH: {fmtNum(reading.ph, 2)}</div>}
                  {reading?.turbidity != null && (
                    <div>Turbidity: {fmtNum(reading.turbidity, 1)} NTU</div>
                  )}
                  {reading && <div className="text-slate-500">{fmtAgo(reading.timestamp)}</div>}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
