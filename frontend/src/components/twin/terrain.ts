/**
 * Nimba terrain projection + elevation sampling.
 *
 * The DEM payload at /dem/nimba.json is a 180x180 grid of elevations
 * extracted from Copernicus GLO-30 covering 7.50-7.70 N, 8.60-8.40 W
 * — real Mount Nimba (summit 1752m) + the Yekepa / Tokadeh area.
 *
 * The twin uses a world-space scale where 1 Three.js unit = 100 m, so a
 * 22 km x 22 km tile fits inside a 220-unit footprint comfortable for
 * the orbit camera. Elevations are not exaggerated — real meters on the
 * same 1-unit = 100 m scale, so the mountain reads ~17 units tall
 * against its ~400 m valley floor, which matches a surveyor's eye.
 */

export interface Dem {
  format: 'geosentinel.dem.v1';
  source: string;
  bounds: {
    min_lon: number;
    min_lat: number;
    max_lon: number;
    max_lat: number;
    rows: number;
    cols: number;
    min_elev: number;
    max_elev: number;
  };
  grid: { rows: number; cols: number; cell_m_lon: number; cell_m_lat: number };
  extent_m: { width: number; height: number };
  elevation_m: { min: number; max: number };
  elevations: number[][];
  attribution: string;
}

export const DEM_URL = '/dem/nimba.json';
export const METERS_PER_UNIT = 100;

/** Convert a (lat, lng) pair to local terrain coordinates (x, z) in
 * Three.js units. +X points east, +Z points south (right-handed). */
export function latLngToXZ(dem: Dem, lat: number, lng: number): [number, number] {
  const { min_lon, min_lat, max_lon, max_lat } = dem.bounds;
  const widthM = dem.extent_m.width;
  const heightM = dem.extent_m.height;
  const u = (lng - min_lon) / (max_lon - min_lon); // 0..1 west->east
  const v = (lat - min_lat) / (max_lat - min_lat); // 0..1 south->north
  const centeredU = u - 0.5;
  const centeredV = v - 0.5;
  const x = (centeredU * widthM) / METERS_PER_UNIT;
  // Z grows south in our scene; v=1 (north) -> z = -height/2.
  const z = (-centeredV * heightM) / METERS_PER_UNIT;
  return [x, z];
}

/** Bilinear elevation sample (meters) at a lat/lng, converted to Three.js
 * units via METERS_PER_UNIT. Returns null if outside the DEM. */
export function sampleElevation(dem: Dem, lat: number, lng: number): number | null {
  const { min_lon, min_lat, max_lon, max_lat, rows, cols } = dem.bounds;
  if (lat < min_lat || lat > max_lat || lng < min_lon || lng > max_lon) return null;
  const u = (lng - min_lon) / (max_lon - min_lon); // 0..1
  const v = 1 - (lat - min_lat) / (max_lat - min_lat); // row 0 is north
  const colf = u * (cols - 1);
  const rowf = v * (rows - 1);
  const c0 = Math.floor(colf);
  const r0 = Math.floor(rowf);
  const c1 = Math.min(cols - 1, c0 + 1);
  const r1 = Math.min(rows - 1, r0 + 1);
  const tc = colf - c0;
  const tr = rowf - r0;
  const e00 = dem.elevations[r0][c0];
  const e01 = dem.elevations[r0][c1];
  const e10 = dem.elevations[r1][c0];
  const e11 = dem.elevations[r1][c1];
  const top = e00 * (1 - tc) + e01 * tc;
  const bot = e10 * (1 - tc) + e11 * tc;
  const elevM = top * (1 - tr) + bot * tr;
  return elevM / METERS_PER_UNIT;
}

/** Earth-tone color ramp by elevation (meters). Muted so the terrain
 * reads as cartographic surface, not a video-game palette. */
export function elevationColor(elevM: number, minM: number, maxM: number): [number, number, number] {
  const t = Math.max(0, Math.min(1, (elevM - minM) / Math.max(1, maxM - minM)));
  // 5 stops: valley sand -> olive -> dark green -> rust -> rock gray
  const stops: Array<[number, [number, number, number]]> = [
    [0.0, [0.47, 0.42, 0.33]],
    [0.25, [0.40, 0.44, 0.30]],
    [0.5, [0.32, 0.36, 0.26]],
    [0.75, [0.42, 0.33, 0.26]],
    [1.0, [0.56, 0.54, 0.50]],
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    const [t0, c0] = stops[i];
    const [t1, c1] = stops[i + 1];
    if (t >= t0 && t <= t1) {
      const k = (t - t0) / (t1 - t0);
      return [c0[0] + (c1[0] - c0[0]) * k, c0[1] + (c1[1] - c0[1]) * k, c0[2] + (c1[2] - c0[2]) * k];
    }
  }
  return stops[stops.length - 1][1];
}
