/**
 * ASM licence + protected-area reference overlay for the "where can I mine?"
 * screen. First-pass dataset covering the Nimba range (matching the
 * hillshade tile we ship) with representative polygons derived from
 * public MME, EPA, and FDA descriptions in the programme brief.
 *
 * PRE-INCUBATION TODO: replace these with the authoritative GeoJSON from
 * the MME Online Repository (launched Dec 2025) and FDA's protected-area
 * registry. Coordinates below are approximations in [lng, lat] order,
 * suitable for a mobile MVP that answers "is this spot likely GREEN /
 * YELLOW / RED" within the Nimba window.
 */

export type ZoneCategory =
  | 'LICENCE_ASM' // Class C gold / diamond ASM licence — permitted for cooperative members
  | 'LICENCE_EXPLORATION' // Corporate exploration licence — cooperative permission required
  | 'PROTECTED_AREA' // National park / strict nature reserve — forbidden
  | 'COMMUNITY_FOREST'; // Legally protected community land — permission required

export interface Zone {
  id: string;
  name: string;
  category: ZoneCategory;
  // Simple polygon as an array of [lng, lat] pairs forming a closed ring
  // (first and last points equal).
  polygon: [number, number][];
  notes?: string;
}

/**
 * Nimba window: lat 7.50-7.70, lng -8.60 to -8.40. All zones below sit
 * inside the Copernicus GLO-30 hillshade tile the app bundles.
 */
export const ZONES: Zone[] = [
  {
    id: 'east-nimba-reserve',
    name: 'East Nimba Nature Reserve',
    category: 'PROTECTED_AREA',
    notes: 'FDA strict nature reserve. Mining is prohibited.',
    polygon: [
      [-8.470, 7.580],
      [-8.420, 7.580],
      [-8.410, 7.620],
      [-8.430, 7.660],
      [-8.470, 7.655],
      [-8.480, 7.620],
      [-8.470, 7.580],
    ],
  },
  {
    id: 'amli-concession-core',
    name: 'ArcelorMittal Liberia concession (Yekepa/Tokadeh)',
    category: 'LICENCE_EXPLORATION',
    notes: 'Corporate iron-ore concession. ASM entry requires written cooperative agreement with AML.',
    polygon: [
      [-8.570, 7.550],
      [-8.450, 7.550],
      [-8.450, 7.605],
      [-8.570, 7.605],
      [-8.570, 7.550],
    ],
  },
  {
    id: 'tokadeh-community-forest',
    name: 'Tokadeh community forest',
    category: 'COMMUNITY_FOREST',
    notes: 'Legally recognised community land. Mining permitted only with Local Consultative Forum consent.',
    polygon: [
      [-8.590, 7.520],
      [-8.550, 7.520],
      [-8.550, 7.555],
      [-8.590, 7.555],
      [-8.590, 7.520],
    ],
  },
  {
    id: 'yekepa-asm-cluster',
    name: 'Yekepa ASM Class C cluster (indicative)',
    category: 'LICENCE_ASM',
    notes: 'Grouping of Class C gold ASM licences in the Yekepa drainage. Verify your individual permit with MME.',
    polygon: [
      [-8.560, 7.560],
      [-8.520, 7.560],
      [-8.520, 7.590],
      [-8.560, 7.590],
      [-8.560, 7.560],
    ],
  },
];

/** Return the hex color used to paint a given zone on the SVG overlay. */
export function zoneColor(category: ZoneCategory): string {
  switch (category) {
    case 'LICENCE_ASM':
      return '#2BB07A';
    case 'LICENCE_EXPLORATION':
      return '#60A5FA';
    case 'COMMUNITY_FOREST':
      return '#F59E0B';
    case 'PROTECTED_AREA':
      return '#EF4444';
  }
}

/** Human-readable status derived from the zones a point falls inside. */
export interface LocationVerdict {
  tier: 'GREEN' | 'YELLOW' | 'RED' | 'UNKNOWN';
  headline: string;
  detail: string;
  zones: Zone[];
}

/** Point-in-polygon (ray casting). Returns true when (lng, lat) is inside. */
export function pointInPolygon(lng: number, lat: number, polygon: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    const intersects =
      yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-12) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

/** Classify a GPS point against the bundled zones. First-pass logic:
 *  RED  if inside a PROTECTED_AREA
 *  YELLOW if inside only LICENCE_EXPLORATION or COMMUNITY_FOREST
 *  GREEN  if inside a LICENCE_ASM polygon (and NOT inside a protected area)
 *  UNKNOWN if outside everything we have data for.
 */
export function classifyLocation(lng: number, lat: number): LocationVerdict {
  const hits = ZONES.filter((z) => pointInPolygon(lng, lat, z.polygon));
  const protectedHits = hits.filter((z) => z.category === 'PROTECTED_AREA');
  const asmHits = hits.filter((z) => z.category === 'LICENCE_ASM');
  const explorationHits = hits.filter((z) => z.category === 'LICENCE_EXPLORATION');
  const communityHits = hits.filter((z) => z.category === 'COMMUNITY_FOREST');

  if (protectedHits.length > 0) {
    return {
      tier: 'RED',
      headline: 'No mining here',
      detail: `${protectedHits[0].name}. ${protectedHits[0].notes ?? ''}`.trim(),
      zones: hits,
    };
  }
  if (asmHits.length > 0) {
    return {
      tier: 'GREEN',
      headline: 'Mining is permitted',
      detail: `Inside ${asmHits[0].name}. Confirm your personal Class C permit covers this exact pit.`,
      zones: hits,
    };
  }
  if (explorationHits.length > 0) {
    return {
      tier: 'YELLOW',
      headline: 'Cooperative permission required',
      detail: `${explorationHits[0].name}. ${explorationHits[0].notes ?? ''}`.trim(),
      zones: hits,
    };
  }
  if (communityHits.length > 0) {
    return {
      tier: 'YELLOW',
      headline: 'Community-land rules apply',
      detail: `${communityHits[0].name}. ${communityHits[0].notes ?? ''}`.trim(),
      zones: hits,
    };
  }
  return {
    tier: 'UNKNOWN',
    headline: 'No data for this location',
    detail: 'This point falls outside the areas covered by the current offline tile. Download more tiles when you have signal.',
    zones: [],
  };
}
