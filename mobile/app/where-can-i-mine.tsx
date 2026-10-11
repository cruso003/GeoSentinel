import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Circle, Polygon } from 'react-native-svg';
import * as Location from 'expo-location';
import { colors } from '../src/theme/colors';
import { ZONES, classifyLocation, zoneColor } from '../src/data/liberia-zones';

// Window of the bundled Nimba hillshade (matches assets/nimba-dem.json).
const BOUNDS = { minLat: 7.5, maxLat: 7.7, minLng: -8.6, maxLng: -8.4 };

function latLngToPct(lat: number, lng: number) {
  const xPct = ((lng - BOUNDS.minLng) / (BOUNDS.maxLng - BOUNDS.minLng)) * 100;
  // SVG Y grows down; latitude grows up, so invert.
  const yPct = (1 - (lat - BOUNDS.minLat) / (BOUNDS.maxLat - BOUNDS.minLat)) * 100;
  return { xPct, yPct };
}

type Verdict = ReturnType<typeof classifyLocation>;

export default function WhereCanIMineScreen() {
  const { width } = useWindowDimensions();
  const mapHeight = Math.min(width - 32, 420);

  const [permissionState, setPermissionState] =
    useState<'idle' | 'requesting' | 'granted' | 'denied'>('idle');
  const [coords, setCoords] = useState<Location.LocationObjectCoords | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [demoMode, setDemoMode] = useState(false);

  const requestFix = async () => {
    setError(null);
    setPermissionState('requesting');
    try {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (perm.status !== 'granted') {
        setPermissionState('denied');
        setError('Location permission was declined. Enable it in Settings to check your spot.');
        return;
      }
      setPermissionState('granted');
      const pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      setCoords(pos.coords);
      setDemoMode(false);
      setVerdict(classifyLocation(pos.coords.longitude, pos.coords.latitude));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not read your GPS position.');
      setPermissionState('denied');
    }
  };

  // Demo pin — drops a point inside the sample zones so a user without
  // GPS access (demo laptop, airplane mode) can still see the flow.
  const dropDemoPin = (name: 'yekepa' | 'east-nimba-reserve' | 'community-forest') => {
    const pin = {
      yekepa: { lat: 7.573, lng: -8.544 },
      'east-nimba-reserve': { lat: 7.615, lng: -8.445 },
      'community-forest': { lat: 7.538, lng: -8.572 },
    }[name];
    setCoords({
      latitude: pin.lat,
      longitude: pin.lng,
      accuracy: 25,
      altitude: null,
      altitudeAccuracy: null,
      heading: null,
      speed: null,
    });
    setDemoMode(true);
    setVerdict(classifyLocation(pin.lng, pin.lat));
  };

  useEffect(() => {
    // Attempt an auto-fix on mount so the user who taps the card from home
    // doesn't have to tap again. If permission isn't granted we fall back
    // to the manual button + demo pins.
    requestFix();
  }, []);

  const pinPct = useMemo(() => {
    if (!coords) return null;
    return latLngToPct(coords.latitude, coords.longitude);
  }, [coords]);

  const inWindow = useMemo(() => {
    if (!coords) return true;
    return (
      coords.latitude >= BOUNDS.minLat &&
      coords.latitude <= BOUNDS.maxLat &&
      coords.longitude >= BOUNDS.minLng &&
      coords.longitude <= BOUNDS.maxLng
    );
  }, [coords]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bgDeep }} edges={['bottom']}>
      <View style={styles.content}>
        <Text style={styles.hint}>
          Your location is checked against licence boundaries bundled with the app. The hillshade is
          Nimba, from Copernicus GLO-30 (ESA). More regions ship as we add them.
        </Text>

        {/* Map tile — hillshade background + SVG overlay */}
        <View style={[styles.mapCard, { height: mapHeight }]}>
          <Image
            source={require('../assets/nimba-hillshade.png')}
            style={styles.mapImage}
            resizeMode="cover"
            accessibilityLabel="Nimba range hillshade, from Copernicus GLO-30"
          />
          <Svg
            style={StyleSheet.absoluteFill}
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
          >
            {ZONES.map((zone) => {
              const points = zone.polygon
                .map(([lng, lat]) => {
                  const { xPct, yPct } = latLngToPct(lat, lng);
                  return `${xPct.toFixed(2)},${yPct.toFixed(2)}`;
                })
                .join(' ');
              return (
                <Polygon
                  key={zone.id}
                  points={points}
                  fill={zoneColor(zone.category)}
                  fillOpacity={0.3}
                  stroke={zoneColor(zone.category)}
                  strokeWidth={0.2}
                  vectorEffect="non-scaling-stroke"
                />
              );
            })}
            {pinPct && inWindow && (
              <>
                <Circle
                  cx={pinPct.xPct}
                  cy={pinPct.yPct}
                  r={1.2}
                  fill="#FBFBF8"
                  stroke="#0F1F36"
                  strokeWidth={0.4}
                  vectorEffect="non-scaling-stroke"
                />
                <Circle
                  cx={pinPct.xPct}
                  cy={pinPct.yPct}
                  r={2.4}
                  fill="transparent"
                  stroke="#FBFBF8"
                  strokeWidth={0.3}
                  strokeOpacity={0.6}
                  vectorEffect="non-scaling-stroke"
                />
              </>
            )}
          </Svg>
          <View style={styles.scaleTag}>
            <Text style={styles.scaleTagText}>
              N ↑ · ≈ 22 km across · Nimba window
            </Text>
          </View>
          <View style={styles.attribution}>
            <Text style={styles.attributionText}>
              Terrain: Copernicus GLO-30 (ESA) · offline-rendered
            </Text>
          </View>
        </View>

        {/* Verdict card — the whole point of the screen */}
        {verdict ? (
          <View style={[styles.verdictCard, verdictStyle(verdict.tier)]}>
            <View style={styles.verdictHeaderRow}>
              <View style={[styles.verdictBadge, verdictBadgeStyle(verdict.tier)]}>
                <Text style={styles.verdictBadgeText}>{verdict.tier}</Text>
              </View>
              {demoMode ? (
                <Text style={styles.verdictDemoTag}>DEMO PIN</Text>
              ) : coords ? (
                <Text style={styles.verdictDemoTag}>
                  ±{coords.accuracy ? Math.round(coords.accuracy) : '—'} m
                </Text>
              ) : null}
            </View>
            <Text style={styles.verdictHeadline}>{verdict.headline}</Text>
            <Text style={styles.verdictDetail}>{verdict.detail}</Text>
            {coords && (
              <Text style={styles.verdictCoords}>
                {coords.latitude.toFixed(5)}°, {coords.longitude.toFixed(5)}°
                {!inWindow ? '  ·  outside bundled tile' : ''}
              </Text>
            )}
          </View>
        ) : permissionState === 'requesting' ? (
          <View style={styles.loadingCard}>
            <ActivityIndicator color={colors.good} />
            <Text style={styles.loadingText}>Getting your position…</Text>
          </View>
        ) : (
          <View style={styles.loadingCard}>
            <Text style={styles.loadingText}>Waiting for GPS or a demo pin.</Text>
          </View>
        )}

        {error && (
          <View style={styles.errorCard}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        {/* Actions — real fix + 3 demo pins so a reviewer with no GPS can test every tier */}
        <View style={styles.actionsRow}>
          <Pressable
            onPress={requestFix}
            style={({ pressed }) => [styles.actionPrimary, pressed && styles.actionPressed]}
          >
            <Text style={styles.actionPrimaryText}>Use my real GPS</Text>
          </Pressable>
        </View>
        <View style={styles.demoRow}>
          <Pressable
            onPress={() => dropDemoPin('yekepa')}
            style={({ pressed }) => [
              styles.demoChip,
              { borderColor: colors.good },
              pressed && styles.actionPressed,
            ]}
          >
            <Text style={[styles.demoChipText, { color: colors.good }]}>Demo: Yekepa (GREEN)</Text>
          </Pressable>
          <Pressable
            onPress={() => dropDemoPin('community-forest')}
            style={({ pressed }) => [
              styles.demoChip,
              { borderColor: colors.caution },
              pressed && styles.actionPressed,
            ]}
          >
            <Text style={[styles.demoChipText, { color: colors.caution }]}>Demo: Community forest (YELLOW)</Text>
          </Pressable>
          <Pressable
            onPress={() => dropDemoPin('east-nimba-reserve')}
            style={({ pressed }) => [
              styles.demoChip,
              { borderColor: colors.critical },
              pressed && styles.actionPressed,
            ]}
          >
            <Text style={[styles.demoChipText, { color: colors.critical }]}>Demo: East Nimba Reserve (RED)</Text>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

function verdictStyle(tier: Verdict['tier']) {
  switch (tier) {
    case 'GREEN':
      return { backgroundColor: '#0E3B2A', borderColor: colors.good };
    case 'YELLOW':
      return { backgroundColor: '#3F2E12', borderColor: colors.caution };
    case 'RED':
      return { backgroundColor: '#3B1414', borderColor: colors.critical };
    default:
      return { backgroundColor: colors.bgPanel, borderColor: colors.bgLine };
  }
}

function verdictBadgeStyle(tier: Verdict['tier']) {
  switch (tier) {
    case 'GREEN':
      return { backgroundColor: colors.good };
    case 'YELLOW':
      return { backgroundColor: colors.caution };
    case 'RED':
      return { backgroundColor: colors.critical };
    default:
      return { backgroundColor: colors.textMuted };
  }
}

const styles = StyleSheet.create({
  content: {
    flex: 1,
    padding: 16,
    gap: 14,
  },
  hint: {
    color: colors.textMuted,
    fontSize: 12,
    lineHeight: 18,
  },
  mapCard: {
    borderRadius: 16,
    overflow: 'hidden',
    backgroundColor: colors.bgSurface,
    borderWidth: 1,
    borderColor: colors.bgLine,
    position: 'relative',
  },
  mapImage: {
    width: '100%',
    height: '100%',
  },
  scaleTag: {
    position: 'absolute',
    top: 8,
    right: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: 'rgba(15,31,54,0.8)',
    borderWidth: 1,
    borderColor: colors.bgLine,
  },
  scaleTagText: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '500',
  },
  attribution: {
    position: 'absolute',
    bottom: 6,
    right: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    backgroundColor: 'rgba(15,31,54,0.8)',
    borderWidth: 1,
    borderColor: colors.bgLine,
  },
  attributionText: {
    color: colors.textMuted,
    fontSize: 9,
  },
  verdictCard: {
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    gap: 8,
  },
  verdictHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  verdictBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  verdictBadgeText: {
    color: '#07131F',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1,
  },
  verdictDemoTag: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '500',
    letterSpacing: 1,
  },
  verdictHeadline: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: '700',
  },
  verdictDetail: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
  },
  verdictCoords: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 4,
  },
  loadingCard: {
    padding: 20,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.bgLine,
    backgroundColor: colors.bgPanel,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    justifyContent: 'center',
  },
  loadingText: {
    color: colors.textSecondary,
    fontSize: 14,
  },
  errorCard: {
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.alert,
    backgroundColor: '#3B1414',
  },
  errorText: {
    color: colors.textPrimary,
    fontSize: 13,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 10,
  },
  actionPrimary: {
    flex: 1,
    backgroundColor: colors.good,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  actionPrimaryText: {
    color: colors.textDark,
    fontSize: 15,
    fontWeight: '700',
  },
  actionPressed: {
    opacity: 0.75,
  },
  demoRow: {
    gap: 8,
  },
  demoChip: {
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    backgroundColor: colors.bgSurface,
    alignItems: 'center',
  },
  demoChipText: {
    fontSize: 13,
    fontWeight: '600',
  },
});
