import { Html } from '@react-three/drei';
import { useState } from 'react';
import { MOCK_NODES } from '@/mock/site';
import { useSensorStore } from '@/store/sensorStore';
import { fmtNum } from '@/utils/format';
import { latLngToXZ, sampleElevation, type Dem } from './terrain';

const NODE_COLORS: Record<string, string> = {
  ONLINE: '#10B981',
  DEGRADED: '#F59E0B',
  OFFLINE: '#EF4444',
};

/** Project a (lat, lng) onto the loaded DEM. Returns the sensor's
 * position in Three.js units with Y lifted a little above the mesh so
 * it reads as planted on the surface rather than embedded in it.
 * Falls back to a flat scene centre when the DEM hasn't loaded yet. */
function projectOnDem(dem: Dem | null, lat: number, lng: number): [number, number, number] {
  if (!dem) return [0, 0.5, 0];
  const [x, z] = latLngToXZ(dem, lat, lng);
  const yElev = sampleElevation(dem, lat, lng);
  const y = (yElev ?? 5) + 0.5;
  return [x, y, z];
}

interface Props {
  dem: Dem | null;
  visible?: boolean;
  showLabels?: boolean;
}

export function SensorMarkers({ dem, visible = true, showLabels = true }: Props) {
  const env = useSensorStore((s) => s.latestEnvReadings);
  const geo = useSensorStore((s) => s.latestGeoReadings);
  const [hovered, setHovered] = useState<string | null>(null);

  if (!visible) return null;

  return (
    <group>
      {MOCK_NODES.map((node) => {
        const pos = projectOnDem(dem, node.lat, node.lng);
        const color = NODE_COLORS[node.status] ?? '#94A3B8';
        const reading = node.node_type === 'ENVIRONMENTAL' ? env[node.id] : geo[node.id];
        return (
          <group key={node.id} position={pos}>
            <mesh
              onPointerOver={() => setHovered(node.id)}
              onPointerOut={() => setHovered(null)}
            >
              <sphereGeometry args={[0.4, 16, 16]} />
              <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6} />
            </mesh>
            {/* Pole from the surface to the marker so a flat valley node
                still catches the eye against the terrain colour. */}
            <mesh position={[0, -0.6, 0]}>
              <cylinderGeometry args={[0.06, 0.06, 1.2, 8]} />
              <meshStandardMaterial color="#0F1F36" />
            </mesh>
            {(showLabels || hovered === node.id) && (
              <Html distanceFactor={60} position={[0, 1.2, 0]} center>
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
