import { useMemo } from 'react';
import * as THREE from 'three';

// Procedurally generated open-pit cone frustum (Spec 7.6.1).
// Outer rim radius decreasing as you descend in benches.
export function MinePit() {
  const geometry = useMemo(() => {
    const benches = 6;
    const rimR = 80;
    const benchH = -8;
    const benchStep = 7; // horizontal step inward per bench
    const segments = 48;
    const positions: number[] = [];
    const indices: number[] = [];
    const colors: number[] = [];

    // Generate rings
    for (let b = 0; b <= benches; b++) {
      const r = rimR - b * benchStep;
      const y = b * benchH;
      for (let s = 0; s < segments; s++) {
        const theta = (s / segments) * Math.PI * 2;
        // Add bench-edge wobble for realism.
        const wobble = 0.6 * Math.sin(theta * 5 + b);
        const x = (r + wobble) * Math.cos(theta);
        const z = (r + wobble) * Math.sin(theta);
        positions.push(x, y, z);
        const t = b / benches;
        // Tan -> dark brown gradient.
        colors.push(0.55 - t * 0.25, 0.42 - t * 0.2, 0.32 - t * 0.18);
      }
    }

    // Connect rings into a strip
    for (let b = 0; b < benches; b++) {
      for (let s = 0; s < segments; s++) {
        const a = b * segments + s;
        const bIdx = b * segments + ((s + 1) % segments);
        const c = (b + 1) * segments + s;
        const d = (b + 1) * segments + ((s + 1) % segments);
        indices.push(a, c, bIdx);
        indices.push(bIdx, c, d);
      }
    }

    // Floor cap
    const floorStart = positions.length / 3;
    positions.push(0, benches * benchH, 0);
    colors.push(0.25, 0.2, 0.18);
    for (let s = 0; s < segments; s++) {
      const a = benches * segments + s;
      const bIdx = benches * segments + ((s + 1) % segments);
      indices.push(a, bIdx, floorStart);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    geo.setIndex(indices);
    geo.computeVertexNormals();
    return geo;
  }, []);

  return (
    <mesh geometry={geometry} receiveShadow>
      <meshStandardMaterial vertexColors flatShading metalness={0.05} roughness={0.95} />
    </mesh>
  );
}
