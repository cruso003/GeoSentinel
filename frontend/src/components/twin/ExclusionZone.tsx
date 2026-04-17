import { useMemo } from 'react';
import * as THREE from 'three';
import { useAIStore } from '@/store/aiStore';
import { MOCK_SLOPES } from '@/mock/site';

// Renders a translucent red volume above any slope at CRITICAL/EVACUATION tier.
export function ExclusionZone({ visible = true }: { visible?: boolean }) {
  const slopes = useAIStore((s) => s.slopeWatchPredictions);

  const zones = useMemo(
    () =>
      MOCK_SLOPES.map((slope) => {
        const verts = slope.mesh_vertices;
        const cx = verts.reduce((a, v) => a + v[0], 0) / verts.length;
        const cy = verts.reduce((a, v) => a + v[1], 0) / verts.length;
        const cz = verts.reduce((a, v) => a + v[2], 0) / verts.length;
        return { id: slope.id, center: [cx, cy, cz] as [number, number, number] };
      }),
    [],
  );

  if (!visible) return null;

  return (
    <group>
      {zones.map(({ id, center }) => {
        const tier = slopes[id]?.alert_tier;
        if (tier !== 'CRITICAL' && tier !== 'EVACUATION') return null;
        return (
          <mesh key={id} position={[center[0], center[1] + 25, center[2]]}>
            <cylinderGeometry args={[20, 20, 40, 24, 1, true]} />
            <meshStandardMaterial
              color={tier === 'EVACUATION' ? '#7C3AED' : '#EF4444'}
              transparent
              opacity={0.18}
              side={THREE.DoubleSide}
              emissive={tier === 'EVACUATION' ? '#7C3AED' : '#EF4444'}
              emissiveIntensity={0.4}
            />
          </mesh>
        );
      })}
    </group>
  );
}
