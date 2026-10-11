import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Location from 'expo-location';
import * as ImagePicker from 'expo-image-picker';
import { colors } from '../src/theme/colors';
import {
  CONCERN_COLORS,
  CONCERN_LABELS,
  ConcernKind,
  ConcernReport,
  listReports,
  recordReport,
} from '../src/storage/reports';

const KINDS: ConcernKind[] = ['water', 'forest', 'safety', 'mercury', 'other'];

export default function ReportConcernScreen() {
  const [reports, setReports] = useState<ConcernReport[]>([]);
  const [mode, setMode] = useState<'list' | 'form'>('list');
  const [loading, setLoading] = useState(true);

  const reload = async () => setReports(await listReports());

  useEffect(() => {
    (async () => {
      await reload();
      setLoading(false);
    })();
  }, []);

  if (loading) {
    return (
      <SafeAreaView style={styles.flex} edges={['bottom']}>
        <View style={styles.loadingWrap}>
          <Text style={styles.loadingText}>Loading your reports…</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (mode === 'form') {
    return (
      <ReportForm
        onCancel={() => setMode('list')}
        onDone={async () => {
          await reload();
          setMode('list');
        }}
      />
    );
  }

  return <ReportList reports={reports} onNew={() => setMode('form')} />;
}

// --------------------------------------------------------------------------
// List — recent reports (local, awaiting sync)
// --------------------------------------------------------------------------

function ReportList({
  reports,
  onNew,
}: {
  reports: ConcernReport[];
  onNew: () => void;
}) {
  return (
    <SafeAreaView style={styles.flex} edges={['bottom']}>
      <View style={styles.hero}>
        <Text style={styles.sectionLabel}>CONCERNS</Text>
        <Text style={styles.h1}>Report what you see.</Text>
        <Text style={styles.p}>
          Drop a pin + photo + two lines. Reports stay on this phone until you choose to submit;
          submitted reports go to EPA + MME + any operator whose concession the pin falls inside.
        </Text>
      </View>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 10 }}>
        {reports.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>No reports yet</Text>
            <Text style={styles.emptyText}>
              Your first report could be a water discolouration, a tree-clearing you saw today, or
              a pit without proper support. The platform keeps the record even without signal.
            </Text>
          </View>
        ) : (
          reports.map((r) => (
            <View key={r.id} style={styles.reportRow}>
              {r.photoUri ? (
                <Image source={{ uri: r.photoUri }} style={styles.thumb} />
              ) : (
                <View style={[styles.thumb, { alignItems: 'center', justifyContent: 'center' }]}>
                  <Text style={{ color: colors.textMuted, fontSize: 10 }}>no photo</Text>
                </View>
              )}
              <View style={{ flex: 1, gap: 4 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <View style={[styles.kindDot, { backgroundColor: CONCERN_COLORS[r.kind] }]} />
                  <Text style={styles.kindLabel}>{CONCERN_LABELS[r.kind]}</Text>
                  <Text style={styles.syncTag}>{r.syncStatus.toUpperCase()}</Text>
                </View>
                <Text style={styles.reportDesc} numberOfLines={2}>
                  {r.description}
                </Text>
                <Text style={styles.reportMeta}>
                  {new Date(r.createdAt).toLocaleString()}  ·  {r.latitude.toFixed(4)}°, {r.longitude.toFixed(4)}°
                </Text>
              </View>
            </View>
          ))
        )}
      </ScrollView>
      <View style={styles.ctaBar}>
        <Pressable onPress={onNew} style={({ pressed }) => [styles.primaryBtn, pressed && styles.pressed]}>
          <Text style={styles.primaryBtnText}>Report a new concern</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

// --------------------------------------------------------------------------
// Form — pin + photo + text
// --------------------------------------------------------------------------

function ReportForm({
  onCancel,
  onDone,
}: {
  onCancel: () => void;
  onDone: () => void;
}) {
  const [kind, setKind] = useState<ConcernKind>('water');
  const [description, setDescription] = useState('');
  const [reporterName, setReporterName] = useState('');
  const [coords, setCoords] = useState<{
    latitude: number;
    longitude: number;
    accuracyMeters: number | null;
  } | null>(null);
  const [coordState, setCoordState] = useState<'idle' | 'fetching' | 'ok' | 'denied'>('idle');
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const grabGps = async () => {
    setCoordState('fetching');
    try {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (perm.status !== 'granted') {
        setCoordState('denied');
        Alert.alert('Location permission denied', 'Enable location to pin the report. You can also enter coordinates manually below.');
        return;
      }
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setCoords({
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        accuracyMeters: pos.coords.accuracy ?? null,
      });
      setCoordState('ok');
    } catch (e) {
      setCoordState('denied');
      Alert.alert('Could not read GPS', e instanceof Error ? e.message : String(e));
    }
  };

  const pickPhoto = async (source: 'camera' | 'library') => {
    try {
      let perm;
      if (source === 'camera') {
        perm = await ImagePicker.requestCameraPermissionsAsync();
      } else {
        perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      }
      if (perm.status !== 'granted') {
        Alert.alert('Permission denied', 'Can\'t add a photo without permission.');
        return;
      }
      const res =
        source === 'camera'
          ? await ImagePicker.launchCameraAsync({ quality: 0.6, allowsEditing: false })
          : await ImagePicker.launchImageLibraryAsync({ quality: 0.6, allowsEditing: false, mediaTypes: ImagePicker.MediaTypeOptions.Images });
      if (!res.canceled && res.assets && res.assets[0]) {
        setPhotoUri(res.assets[0].uri);
      }
    } catch (e) {
      Alert.alert('Could not add photo', e instanceof Error ? e.message : String(e));
    }
  };

  const canSubmit =
    description.trim().length >= 3 &&
    coords !== null &&
    isFinite(coords.latitude) &&
    isFinite(coords.longitude);

  const submit = async () => {
    if (!canSubmit || busy || !coords) return;
    setBusy(true);
    try {
      await recordReport({
        kind,
        description,
        latitude: coords.latitude,
        longitude: coords.longitude,
        accuracyMeters: coords.accuracyMeters,
        photoUri,
        reporterName,
      });
      onDone();
    } catch (e) {
      Alert.alert('Could not save', e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.flex} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.formPad}>
        <Text style={styles.sectionLabel}>NEW REPORT</Text>
        <Text style={styles.h1}>What did you see?</Text>

        <View style={styles.fieldWrap}>
          <Text style={styles.fieldLabel}>Concern type</Text>
          <View style={styles.kindGrid}>
            {KINDS.map((k) => (
              <Pressable
                key={k}
                onPress={() => setKind(k)}
                style={({ pressed }) => [
                  styles.kindChip,
                  { borderColor: CONCERN_COLORS[k] },
                  kind === k && { backgroundColor: CONCERN_COLORS[k] },
                  pressed && styles.pressed,
                ]}
              >
                <Text
                  style={[
                    styles.kindChipText,
                    { color: kind === k ? colors.textDark : CONCERN_COLORS[k] },
                  ]}
                >
                  {CONCERN_LABELS[k]}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        <View style={styles.fieldWrap}>
          <Text style={styles.fieldLabel}>Description</Text>
          <TextInput
            value={description}
            onChangeText={setDescription}
            placeholder="e.g. Discoloured water in the creek near our pit, started yesterday afternoon."
            placeholderTextColor={colors.textMuted}
            style={[styles.field, { minHeight: 100, textAlignVertical: 'top' }]}
            multiline
            autoCorrect
          />
        </View>

        <View style={styles.fieldWrap}>
          <Text style={styles.fieldLabel}>Your name (optional)</Text>
          <TextInput
            value={reporterName}
            onChangeText={setReporterName}
            placeholder="Leave blank to submit anonymously"
            placeholderTextColor={colors.textMuted}
            style={styles.field}
            autoCapitalize="words"
          />
        </View>

        <View style={styles.fieldWrap}>
          <Text style={styles.fieldLabel}>Location</Text>
          <View style={styles.gpsBox}>
            {coords ? (
              <>
                <Text style={styles.gpsCoords}>
                  {coords.latitude.toFixed(5)}°, {coords.longitude.toFixed(5)}°
                </Text>
                <Text style={styles.gpsAcc}>
                  ±{coords.accuracyMeters ? Math.round(coords.accuracyMeters) : '—'} m
                </Text>
              </>
            ) : coordState === 'fetching' ? (
              <ActivityIndicator color={colors.good} />
            ) : (
              <Text style={styles.gpsHint}>Tap "Use my current location" to pin this report.</Text>
            )}
          </View>
          <Pressable
            onPress={grabGps}
            style={({ pressed }) => [styles.secondaryBtn, { marginTop: 8 }, pressed && styles.pressed]}
          >
            <Text style={styles.secondaryBtnText}>
              {coords ? 'Refresh location' : 'Use my current location'}
            </Text>
          </Pressable>
        </View>

        <View style={styles.fieldWrap}>
          <Text style={styles.fieldLabel}>Photo (optional, strongly recommended)</Text>
          {photoUri ? (
            <View>
              <Image source={{ uri: photoUri }} style={styles.photoPreview} />
              <Pressable
                onPress={() => setPhotoUri(null)}
                style={({ pressed }) => [styles.linkBtn, pressed && styles.pressed]}
              >
                <Text style={styles.linkBtnText}>Remove photo</Text>
              </Pressable>
            </View>
          ) : (
            <View style={styles.photoRow}>
              <Pressable
                onPress={() => pickPhoto('camera')}
                style={({ pressed }) => [styles.photoChip, pressed && styles.pressed]}
              >
                <Text style={styles.photoChipText}>Take photo</Text>
              </Pressable>
              <Pressable
                onPress={() => pickPhoto('library')}
                style={({ pressed }) => [styles.photoChip, pressed && styles.pressed]}
              >
                <Text style={styles.photoChipText}>From gallery</Text>
              </Pressable>
            </View>
          )}
        </View>

        <View style={styles.btnRow}>
          <Pressable onPress={onCancel} style={({ pressed }) => [styles.secondaryBtn, pressed && styles.pressed]}>
            <Text style={styles.secondaryBtnText}>Cancel</Text>
          </Pressable>
          <Pressable
            disabled={!canSubmit || busy}
            onPress={submit}
            style={({ pressed }) => [
              styles.primaryBtn,
              { flex: 1 },
              !canSubmit && styles.disabledBtn,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.primaryBtnText}>{busy ? 'Saving…' : 'Save report'}</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: colors.bgDeep },
  loadingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: colors.textSecondary, fontSize: 14 },

  hero: {
    paddingHorizontal: 20,
    paddingVertical: 20,
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.bgLine,
    backgroundColor: colors.bgPanel,
  },
  sectionLabel: { color: colors.caution, fontSize: 11, fontWeight: '700', letterSpacing: 2 },
  h1: { color: colors.textPrimary, fontSize: 26, fontWeight: '700' },
  p: { color: colors.textSecondary, fontSize: 13, lineHeight: 19 },

  emptyCard: {
    padding: 24,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.bgLine,
    backgroundColor: colors.bgPanel,
    gap: 8,
    alignItems: 'center',
  },
  emptyTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: '600' },
  emptyText: { color: colors.textSecondary, fontSize: 13, textAlign: 'center', lineHeight: 19 },

  reportRow: {
    flexDirection: 'row',
    padding: 12,
    borderRadius: 12,
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.bgLine,
    gap: 12,
  },
  thumb: {
    width: 72,
    height: 72,
    borderRadius: 8,
    backgroundColor: colors.bgSurface,
    borderWidth: 1,
    borderColor: colors.bgLine,
  },
  kindDot: { width: 10, height: 10, borderRadius: 5 },
  kindLabel: { color: colors.textPrimary, fontSize: 13, fontWeight: '600' },
  syncTag: {
    color: colors.textMuted,
    fontSize: 10,
    marginLeft: 'auto',
    fontWeight: '600',
    letterSpacing: 1,
  },
  reportDesc: { color: colors.textSecondary, fontSize: 13, lineHeight: 18 },
  reportMeta: { color: colors.textMuted, fontSize: 11, fontFamily: 'monospace' },

  formPad: { padding: 20, gap: 14, paddingBottom: 40 },
  fieldWrap: { gap: 6 },
  fieldLabel: { color: colors.textMuted, fontSize: 12, fontWeight: '600', letterSpacing: 0.5 },
  field: {
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.bgLine,
    borderRadius: 10,
    padding: 12,
    color: colors.textPrimary,
    fontSize: 15,
  },

  kindGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  kindChip: {
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: 1,
    backgroundColor: colors.bgSurface,
  },
  kindChipText: { fontSize: 13, fontWeight: '600' },

  gpsBox: {
    minHeight: 60,
    padding: 14,
    borderRadius: 10,
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.bgLine,
    alignItems: 'center',
    justifyContent: 'center',
  },
  gpsCoords: { color: colors.textPrimary, fontSize: 16, fontFamily: 'monospace' },
  gpsAcc: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  gpsHint: { color: colors.textMuted, fontSize: 13, textAlign: 'center' },

  photoRow: { flexDirection: 'row', gap: 10 },
  photoChip: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.bgLine,
    backgroundColor: colors.bgPanel,
    alignItems: 'center',
  },
  photoChipText: { color: colors.textSecondary, fontSize: 14, fontWeight: '600' },
  photoPreview: {
    width: '100%',
    height: 220,
    borderRadius: 10,
    backgroundColor: colors.bgSurface,
    borderWidth: 1,
    borderColor: colors.bgLine,
  },
  linkBtn: { paddingVertical: 10, alignItems: 'center' },
  linkBtnText: { color: colors.alert, fontSize: 13, fontWeight: '600' },

  primaryBtn: {
    backgroundColor: colors.good,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  primaryBtnText: { color: colors.textDark, fontSize: 15, fontWeight: '700' },
  secondaryBtn: {
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.bgLine,
    alignItems: 'center',
    backgroundColor: colors.bgSurface,
  },
  secondaryBtnText: { color: colors.textSecondary, fontSize: 14, fontWeight: '600' },
  disabledBtn: { opacity: 0.4 },
  pressed: { opacity: 0.72 },
  btnRow: { flexDirection: 'row', gap: 10, marginTop: 8 },

  ctaBar: {
    padding: 14,
    borderTopWidth: 1,
    borderTopColor: colors.bgLine,
    backgroundColor: colors.bgDeep,
  },
});
