/**
 * GeoSentinel colour palette, mirrored from the web dashboard so the
 * mobile app and the operator dashboard look like one product.
 * See /frontend/tailwind.config.cjs for the source of truth.
 */

export const colors = {
  // Backgrounds
  bgDeep: '#0F1F36',
  bgPanel: '#152B4A',
  bgLine: '#1F3A5F',
  bgSurface: '#1A1F2E',

  // Text (dark background)
  textPrimary: '#FBFBF8',
  textSecondary: '#BFD8D5',
  textMuted: '#8FA2BA',

  // Text (light background — used in alert sheets on map)
  textDark: '#0F1F36',
  textDarkSecondary: '#4A5568',

  // Status / semantic
  good: '#2BB07A',
  caution: '#F5B041',
  alert: '#D97757',
  critical: '#EF4444',

  // Accent
  brand: '#22D3EE',
  accent: '#2BB07A',

  // Overlays
  licenceClassC: '#2BB07A', // Class C ASM gold — permitted
  licenceExploration: '#60A5FA', // Exploration overlap — cooperative required
  protectedArea: '#EF4444', // Protected areas / parks — forbidden
  communityForest: '#F59E0B', // Community forest — special rules
} as const;

export type ColorKey = keyof typeof colors;
