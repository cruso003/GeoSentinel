import { useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { DEM_URL, METERS_PER_UNIT, elevationColor, type Dem } from './terrain';

/** Real terrain of the Nimba range, built from the Copernicus GLO-30 DEM.
 *
 * The displacement is unexaggerated — vertical and horizontal are the
 * same 1-unit = 100 m scale as the rest of the scene — so Mount Nimba
 * reads ~17 units tall against a ~4-unit valley floor, which matches
 * how a surveyor sees the range in the field, not how a game engine
 * stylises a pit.  Attribution ships beside the model to meet
 * Copernicus terms of use.
 */
export function NimbaTerrain({ onLoad }: { onLoad?: (dem: Dem) => void } = {}) {
  const [dem, setDem] = useState<Dem | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(DEM_URL)
      .then((r) => r.json())
      .then((data: Dem) => {
        if (!cancelled) {
          setDem(data);
          onLoad?.(data);
        }
      })
      .catch((err) => {
        console.error('[NimbaTerrain] failed to load DEM:', err);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const geometry = useMemo(() => {
    if (!dem) return null;
    const rows = dem.bounds.rows;
    const cols = dem.bounds.cols;
    const widthUnits = dem.extent_m.width / METERS_PER_UNIT;
    const heightUnits = dem.extent_m.height / METERS_PER_UNIT;
    // PlaneGeometry is on the XZ plane after rotation; we build it
    // directly from the elevation grid.
    const geo = new THREE.PlaneGeometry(widthUnits, heightUnits, cols - 1, rows - 1);
    geo.rotateX(-Math.PI / 2);
    const positions = geo.attributes.position as THREE.BufferAttribute;
    const colors = new Float32Array(positions.count * 3);
    const minM = dem.elevation_m.min;
    const maxM = dem.elevation_m.max;
    // Vertices are generated in row-major order from (-w/2, -h/2) -> (+w/2, +h/2).
    // After the X rotation, the Y of each vertex becomes the displaced height.
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const i = r * cols + c;
        // Elevations grid: row 0 is north; PlaneGeometry row 0 is -h/2
        // (which, after our camera orientation, is "far"). Flip so north
        // in the data ends up at -Z in the scene (consistent with
        // SensorMarkers' projection in terrain.ts).
        const elevM = dem.elevations[r][c];
        positions.setY(i, elevM / METERS_PER_UNIT);
        const [cr, cg, cb] = elevationColor(elevM, minM, maxM);
        colors[i * 3] = cr;
        colors[i * 3 + 1] = cg;
        colors[i * 3 + 2] = cb;
      }
    }
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geo.computeVertexNormals();
    return geo;
  }, [dem]);

  if (!geometry) return null;
  return (
    <mesh geometry={geometry} receiveShadow castShadow>
      <meshStandardMaterial vertexColors flatShading metalness={0.02} roughness={0.95} />
    </mesh>
  );
}
