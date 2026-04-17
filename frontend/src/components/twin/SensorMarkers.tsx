import { Html } from '@react-three/drei';
import { useState } from 'react';
import { MOCK_NODES, MOCK_SITE } from '@/mock/site';
import { useSensorStore } from '@/store/sensorStore';
import { fmtNum } from '@/utils/format';

const NODE_COLORS: Record<string, string> = {
  ONLINE: '#10B981',
  DEGRADED: '#F59E0B',
  OFFLINE: '#EF4444',
};

// Project lat/lng to local pit coordinates by linear scaling (Phase 1).
function project(lat: number, lng: number): [number, number, number] {
  const cx = MOCK_SITE.centroid.lat;
  const cy = MOCK_SITE.centroid.lng;
  // ~111km / degree lat; tune to fit the pit cone (~80 unit rim).
  const x = (lng - cy) * 7000;
  const z = -(lat - cx) * 7000;
  return [x, 4, z];
}

export function SensorMarkers({ visible = true, showLabels = true }: { visible?: boolean; showLabels?: boolean }) {
  const env = useSensorStore((s) => s.latestEnvReadings);
  const geo = useSensorStore((s) => s.latestGeoReadings);
  const [hovered, setHovered] = useState<string | null>(null);

  if (!visible) return null;

  return (
    <group>
      {MOCK_NODES.map((node) => {
        const pos = project(node.lat, node.lng);
        const color = NODE_COLORS[node.status] ?? '#94A3B8';
        const reading = node.node_type === 'ENVIRONMENTAL' ? env[node.id] : geo[node.id];
        return (
          <group key={node.id} position={pos}>
            <mesh
              onPointerOver={() => setHovered(node.id)}
              onPointerOut={() => setHovered(null)}
            >
              <sphereGeometry args={[2, 16, 16]} />
              <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6} />
            </mesh>
            {(showLabels || hovered === node.id) && (
              <Html distanceFactor={140} position={[0, 4, 0]} center>
                <div className="rounded bg-bg-deep/90 px-2 py-1 text-[10px] text-slate-100 shadow ring-1 ring-bg-line">
                  <div className="font-bold">{node.id}</div>
                  {reading && 'ph' in reading && reading.ph != null && (
                    <div>pH {fmtNum(reading.ph, 2)}</div>
                  )}
                  {reading && 'pore_pressure' in reading && reading.pore_pressure != null && (
                    <div>PP {fmtNum(reading.pore_pressure, 2)} bar</div>
                  )}
                </div>
              </Html>
            )}
          </group>
        );
      })}
    </group>
  );
}
