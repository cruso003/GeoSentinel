import { useMemo } from 'react';
import * as THREE from 'three';
import { useAIStore } from '@/store/aiStore';
import { MOCK_SLOPES } from '@/mock/site';

function riskColor(score: number): THREE.Color {
  if (score >= 0.7) return new THREE.Color('#EF4444');
  if (score >= 0.45) return new THREE.Color('#F59E0B');
  if (score >= 0.25) return new THREE.Color('#FACC15');
  return new THREE.Color('#10B981');
}

export function SlopeOverlay({ visible = true }: { visible?: boolean }) {
  const slopes = useAIStore((s) => s.slopeWatchPredictions);
  const meshes = useMemo(
    () =>
      MOCK_SLOPES.map((slope) => {
        const verts = slope.mesh_vertices;
        const positions = new Float32Array(verts.flat());
        const indices = [0, 1, 2, 0, 2, 3];
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geo.setIndex(indices);
        geo.computeVertexNormals();
        return { id: slope.id, geo };
      }),
    [],
  );

  if (!visible) return null;

  return (
    <group>
      {meshes.map(({ id, geo }) => {
        const score = slopes[id]?.risk_score ?? 0;
        const color = riskColor(score);
        return (
          <mesh key={id} geometry={geo}>
            <meshStandardMaterial
              color={color}
              transparent
              opacity={0.55}
              side={THREE.DoubleSide}
              emissive={color}
              emissiveIntensity={score * 0.4}
            />
          </mesh>
        );
      })}
    </group>
  );
}
