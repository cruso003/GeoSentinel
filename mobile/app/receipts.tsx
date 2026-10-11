import { useEffect, useState } from 'react';
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '../src/theme/colors';
import {
  Cooperative,
  Receipt,
  fingerprint,
  getCooperative,
  listReceipts,
  recordReceipt,
  setCooperative,
} from '../src/storage/receipts';

type Screen = 'setup' | 'ledger' | 'record' | 'detail';

export default function ReceiptsScreen() {
  const [screen, setScreen] = useState<Screen>('ledger');
  const [coop, setCoop] = useState<Cooperative | null>(null);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [selected, setSelected] = useState<Receipt | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const c = await getCooperative();
      setCoop(c);
      if (!c) setScreen('setup');
      const rs = await listReceipts();
      setReceipts(rs);
      setLoading(false);
    })();
  }, []);

  const reload = async () => {
    const rs = await listReceipts();
    setReceipts(rs);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.flex} edges={['bottom']}>
        <View style={styles.loadingWrap}>
          <Text style={styles.loadingText}>Loading cooperative…</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (screen === 'setup' || !coop) {
    return (
      <CooperativeSetup
        onDone={(c) => {
          setCoop(c);
          setScreen('ledger');
        }}
      />
    );
  }

  if (screen === 'record') {
    return (
      <RecordReceiptForm
        cooperativeId={coop.id}
        onCancel={() => setScreen('ledger')}
        onDone={async (r) => {
          await reload();
          setSelected(r);
          setScreen('detail');
        }}
      />
    );
  }

  if (screen === 'detail' && selected) {
    return (
      <ReceiptDetail
        receipt={selected}
        cooperative={coop}
        onBack={() => setScreen('ledger')}
      />
    );
  }

  return (
    <Ledger
      cooperative={coop}
      receipts={receipts}
      onOpen={(r) => {
        setSelected(r);
        setScreen('detail');
      }}
      onNew={() => setScreen('record')}
    />
  );
}

// --------------------------------------------------------------------------
// Setup — one-time cooperative registration (first time the app opens Receipts)
// --------------------------------------------------------------------------

function CooperativeSetup({ onDone }: { onDone: (c: Cooperative) => void }) {
  const [name, setName] = useState('');
  const [chair, setChair] = useState('');
  const [mineral, setMineral] = useState<Cooperative['mineral']>('gold');
  const [siteNotes, setSiteNotes] = useState('');
  const [busy, setBusy] = useState(false);

  const canSubmit = name.trim().length >= 2 && chair.trim().length >= 2;

  const submit = async () => {
    if (!canSubmit || busy) return;
    setBusy(true);
    try {
      const c = await setCooperative({
        name: name.trim(),
        chairName: chair.trim(),
        mineral,
        siteNotes: siteNotes.trim(),
      });
      onDone(c);
    } catch (e) {
      Alert.alert('Could not save', e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.flex} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.formPad}>
        <Text style={styles.sectionLabel}>FIRST-TIME SETUP</Text>
        <Text style={styles.h1}>Register your cooperative.</Text>
        <Text style={styles.p}>
          Everything stays on this phone until you choose to sync. One cooperative per device.
        </Text>

        <Field label="Cooperative name" value={name} onChangeText={setName} placeholder="e.g. Yekepa Alluvial Diggers" />
        <Field label="Chair name" value={chair} onChangeText={setChair} placeholder="Full name of the chair" />
        <MineralPicker value={mineral} onChange={setMineral} />
        <Field
          label="Site notes (optional)"
          value={siteNotes}
          onChangeText={setSiteNotes}
          placeholder="Approximate location, cooperative registration number"
          multiline
        />

        <Pressable
          disabled={!canSubmit || busy}
          onPress={submit}
          style={({ pressed }) => [
            styles.primaryBtn,
            !canSubmit && styles.disabledBtn,
            pressed && styles.pressed,
          ]}
        >
          <Text style={styles.primaryBtnText}>{busy ? 'Saving…' : 'Register cooperative'}</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

// --------------------------------------------------------------------------
// Ledger — list of past receipts + CTA to record a new one
// --------------------------------------------------------------------------

function Ledger({
  cooperative,
  receipts,
  onOpen,
  onNew,
}: {
  cooperative: Cooperative;
  receipts: Receipt[];
  onOpen: (r: Receipt) => void;
  onNew: () => void;
}) {
  const totalGrams = receipts.reduce((s, r) => s + r.weightGrams, 0);
  const totalUSD = receipts.reduce((s, r) => s + r.totalUSD, 0);
  return (
    <SafeAreaView style={styles.flex} edges={['bottom']}>
      <View style={styles.coopBanner}>
        <Text style={styles.coopName}>{cooperative.name}</Text>
        <Text style={styles.coopMeta}>
          {cooperative.mineral.toUpperCase()} · Chair {cooperative.chairName}
        </Text>
      </View>
      <View style={styles.statsRow}>
        <Stat label="Receipts" value={String(receipts.length)} />
        <Stat label="Total weight" value={`${totalGrams.toFixed(2)} g`} />
        <Stat label="Total paid" value={`$${totalUSD.toFixed(2)}`} />
      </View>
      <ScrollView style={styles.flex} contentContainerStyle={{ padding: 16, gap: 10 }}>
        {receipts.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>No receipts yet</Text>
            <Text style={styles.emptyText}>
              Record your first miner-to-dealer transaction. Each one is hashed and ready to sign.
            </Text>
          </View>
        ) : (
          receipts.map((r) => (
            <Pressable
              key={r.id}
              onPress={() => onOpen(r)}
              style={({ pressed }) => [styles.receiptRow, pressed && styles.pressed]}
            >
              <View style={{ flex: 1 }}>
                <Text style={styles.receiptMiner}>{r.minerName}</Text>
                <Text style={styles.receiptDealer}>sold to {r.dealerName}</Text>
                <Text style={styles.receiptMeta}>
                  {new Date(r.createdAt).toLocaleString()}  ·  {fingerprint(r.integrityHash)}
                </Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={styles.receiptTotal}>${r.totalUSD.toFixed(2)}</Text>
                <Text style={styles.receiptGrams}>{r.weightGrams.toFixed(2)} g · {r.purityPercent}%</Text>
              </View>
            </Pressable>
          ))
        )}
      </ScrollView>
      <View style={styles.ctaBar}>
        <Pressable onPress={onNew} style={({ pressed }) => [styles.primaryBtn, pressed && styles.pressed]}>
          <Text style={styles.primaryBtnText}>Record a sale</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

// --------------------------------------------------------------------------
// Record — the sale form
// --------------------------------------------------------------------------

function RecordReceiptForm({
  cooperativeId,
  onCancel,
  onDone,
}: {
  cooperativeId: string;
  onCancel: () => void;
  onDone: (r: Receipt) => void;
}) {
  const [miner, setMiner] = useState('');
  const [weight, setWeight] = useState('');
  const [purity, setPurity] = useState('91.6'); // 22K default
  const [price, setPrice] = useState('65');
  const [dealer, setDealer] = useState('');
  const [licence, setLicence] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);

  const weightNum = parseFloat(weight);
  const purityNum = parseFloat(purity);
  const priceNum = parseFloat(price);

  const totalUSD =
    isFinite(weightNum) && isFinite(purityNum) && isFinite(priceNum)
      ? weightNum * (purityNum / 100) * priceNum
      : null;

  const canSubmit =
    miner.trim().length > 0 &&
    dealer.trim().length > 0 &&
    isFinite(weightNum) && weightNum > 0 &&
    isFinite(purityNum) && purityNum > 0 && purityNum <= 100 &&
    isFinite(priceNum) && priceNum > 0;

  const submit = async () => {
    if (!canSubmit || busy) return;
    setBusy(true);
    try {
      const r = await recordReceipt({
        cooperativeId,
        minerName: miner,
        weightGrams: weightNum,
        purityPercent: purityNum,
        pricePerGramUSD: priceNum,
        dealerName: dealer,
        dealerLicenceNo: licence,
        notes,
      });
      onDone(r);
    } catch (e) {
      Alert.alert('Could not save', e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.flex} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.formPad}>
        <Text style={styles.sectionLabel}>NEW RECEIPT</Text>
        <Text style={styles.h1}>Record a sale.</Text>

        <Field label="Miner" value={miner} onChangeText={setMiner} placeholder="Full name of the miner" />
        <Field label="Dealer" value={dealer} onChangeText={setDealer} placeholder="Full name of the licensed dealer" />
        <Field
          label="Dealer licence # (optional)"
          value={licence}
          onChangeText={setLicence}
          placeholder="MME dealer licence number"
        />

        <View style={styles.row}>
          <View style={styles.col}>
            <Field label="Weight (grams)" value={weight} onChangeText={setWeight} placeholder="0.0" keyboardType="decimal-pad" />
          </View>
          <View style={styles.col}>
            <Field label="Purity (%)" value={purity} onChangeText={setPurity} placeholder="91.6" keyboardType="decimal-pad" />
          </View>
        </View>
        <Field
          label="Price per gram (USD)"
          value={price}
          onChangeText={setPrice}
          placeholder="65"
          keyboardType="decimal-pad"
        />

        <Field
          label="Notes (optional)"
          value={notes}
          onChangeText={setNotes}
          placeholder="Any notes the miner or dealer want on the receipt"
          multiline
        />

        <View style={styles.totalCard}>
          <Text style={styles.totalLabel}>Total payable</Text>
          <Text style={styles.totalValue}>
            {totalUSD === null ? '—' : `$${totalUSD.toFixed(2)}`}
          </Text>
          <Text style={styles.totalHint}>
            weight × purity × price per gram. Fair-price reference uses the daily USD gold price;
            update it in the Price field above.
          </Text>
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
            <Text style={styles.primaryBtnText}>{busy ? 'Saving…' : 'Save & sign receipt'}</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

// --------------------------------------------------------------------------
// Detail — one receipt, ready to show to buyer / regulator
// --------------------------------------------------------------------------

function ReceiptDetail({
  receipt,
  cooperative,
  onBack,
}: {
  receipt: Receipt;
  cooperative: Cooperative;
  onBack: () => void;
}) {
  return (
    <SafeAreaView style={styles.flex} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.formPad}>
        <Text style={styles.sectionLabel}>RECEIPT</Text>
        <Text style={styles.h1}>${receipt.totalUSD.toFixed(2)}</Text>
        <Text style={styles.p}>
          {receipt.weightGrams.toFixed(2)} g × {receipt.purityPercent}% × ${receipt.pricePerGramUSD.toFixed(2)}/g
        </Text>

        <View style={styles.detailCard}>
          <DetailRow label="Cooperative" value={cooperative.name} />
          <DetailRow label="Miner" value={receipt.minerName} />
          <DetailRow label="Dealer" value={receipt.dealerName} />
          {receipt.dealerLicenceNo && <DetailRow label="Dealer licence" value={receipt.dealerLicenceNo} />}
          <DetailRow label="Date" value={new Date(receipt.createdAt).toLocaleString()} />
          <DetailRow
            label="Signature status"
            value={receipt.signedByBackend ? 'Backend-signed' : 'Local (not yet synced)'}
            tone={receipt.signedByBackend ? 'good' : 'caution'}
          />
          <DetailRow label="Integrity fingerprint" value={fingerprint(receipt.integrityHash)} mono />
        </View>

        {receipt.notes && (
          <View style={styles.notesCard}>
            <Text style={styles.notesLabel}>Notes</Text>
            <Text style={styles.notesText}>{receipt.notes}</Text>
          </View>
        )}

        <View style={styles.integrityCard}>
          <Text style={styles.integrityTitle}>How to verify this receipt</Text>
          <Text style={styles.integrityText}>
            Each receipt stores a SHA-256 hash of its contents. Changing any field — weight, price,
            dealer — changes the hash. When this phone next syncs to the GeoSentinel backend, the
            hash is counter-signed with the project's Ed25519 key and becomes independently
            verifiable by MME or EPA at
            <Text style={styles.mono}>  /api/v1/receipts/{receipt.id}/signature</Text>.
          </Text>
        </View>

        <Pressable onPress={onBack} style={({ pressed }) => [styles.secondaryBtn, pressed && styles.pressed]}>
          <Text style={styles.secondaryBtnText}>Back to ledger</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

// --------------------------------------------------------------------------
// Small building blocks
// --------------------------------------------------------------------------

function Field({
  label,
  value,
  onChangeText,
  placeholder,
  multiline,
  keyboardType,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  placeholder?: string;
  multiline?: boolean;
  keyboardType?: 'default' | 'decimal-pad' | 'numeric';
}) {
  return (
    <View style={styles.fieldWrap}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textMuted}
        style={[styles.field, multiline && styles.fieldMulti]}
        multiline={multiline}
        keyboardType={keyboardType ?? 'default'}
        autoCorrect={false}
        autoCapitalize="words"
      />
    </View>
  );
}

function MineralPicker({
  value,
  onChange,
}: {
  value: Cooperative['mineral'];
  onChange: (v: Cooperative['mineral']) => void;
}) {
  const options: { v: Cooperative['mineral']; label: string }[] = [
    { v: 'gold', label: 'Gold' },
    { v: 'diamond', label: 'Diamond' },
    { v: 'other', label: 'Other' },
  ];
  return (
    <View style={styles.fieldWrap}>
      <Text style={styles.fieldLabel}>Primary mineral</Text>
      <View style={styles.pickerRow}>
        {options.map((o) => (
          <Pressable
            key={o.v}
            onPress={() => onChange(o.v)}
            style={({ pressed }) => [
              styles.pickerChip,
              value === o.v && styles.pickerChipActive,
              pressed && styles.pressed,
            ]}
          >
            <Text style={[styles.pickerChipText, value === o.v && styles.pickerChipTextActive]}>
              {o.label}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  );
}

function DetailRow({
  label,
  value,
  tone,
  mono,
}: {
  label: string;
  value: string;
  tone?: 'good' | 'caution';
  mono?: boolean;
}) {
  const toneColor = tone === 'good' ? colors.good : tone === 'caution' ? colors.caution : colors.textPrimary;
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text
        style={[styles.detailValue, { color: toneColor }, mono && styles.mono]}
      >
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: colors.bgDeep },
  loadingWrap: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: colors.textSecondary, fontSize: 14 },

  formPad: { padding: 20, gap: 14, paddingBottom: 40 },
  sectionLabel: { color: colors.good, fontSize: 11, fontWeight: '700', letterSpacing: 2 },
  h1: { color: colors.textPrimary, fontSize: 28, fontWeight: '700' },
  p: { color: colors.textSecondary, fontSize: 14, lineHeight: 20 },

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
  fieldMulti: { minHeight: 80, textAlignVertical: 'top' },

  row: { flexDirection: 'row', gap: 12 },
  col: { flex: 1 },

  pickerRow: { flexDirection: 'row', gap: 8 },
  pickerChip: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.bgLine,
    alignItems: 'center',
    backgroundColor: colors.bgPanel,
  },
  pickerChipActive: {
    borderColor: colors.good,
    backgroundColor: colors.bgDeep,
  },
  pickerChipText: { color: colors.textSecondary, fontSize: 14, fontWeight: '600' },
  pickerChipTextActive: { color: colors.good },

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

  coopBanner: {
    paddingHorizontal: 20,
    paddingVertical: 14,
    backgroundColor: colors.bgPanel,
    borderBottomWidth: 1,
    borderBottomColor: colors.bgLine,
  },
  coopName: { color: colors.textPrimary, fontSize: 18, fontWeight: '700' },
  coopMeta: { color: colors.textMuted, fontSize: 12, marginTop: 2 },

  statsRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 10,
    backgroundColor: colors.bgSurface,
    borderBottomWidth: 1,
    borderBottomColor: colors.bgLine,
  },
  stat: {
    flex: 1,
    padding: 10,
    borderRadius: 10,
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.bgLine,
  },
  statLabel: { color: colors.textMuted, fontSize: 10, fontWeight: '600', letterSpacing: 1 },
  statValue: { color: colors.textPrimary, fontSize: 18, fontWeight: '700', marginTop: 2 },

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

  receiptRow: {
    flexDirection: 'row',
    padding: 14,
    borderRadius: 12,
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.bgLine,
    gap: 10,
  },
  receiptMiner: { color: colors.textPrimary, fontSize: 15, fontWeight: '600' },
  receiptDealer: { color: colors.textSecondary, fontSize: 13 },
  receiptMeta: { color: colors.textMuted, fontSize: 11, marginTop: 4, fontFamily: 'monospace' },
  receiptTotal: { color: colors.good, fontSize: 16, fontWeight: '700' },
  receiptGrams: { color: colors.textMuted, fontSize: 11, marginTop: 2 },

  ctaBar: {
    padding: 14,
    borderTopWidth: 1,
    borderTopColor: colors.bgLine,
    backgroundColor: colors.bgDeep,
  },

  totalCard: {
    padding: 16,
    borderRadius: 12,
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.bgLine,
    gap: 4,
  },
  totalLabel: { color: colors.textMuted, fontSize: 12, fontWeight: '600', letterSpacing: 1 },
  totalValue: { color: colors.good, fontSize: 32, fontWeight: '700' },
  totalHint: { color: colors.textMuted, fontSize: 11, lineHeight: 16, marginTop: 4 },

  detailCard: {
    padding: 16,
    borderRadius: 12,
    backgroundColor: colors.bgPanel,
    borderWidth: 1,
    borderColor: colors.bgLine,
    gap: 10,
  },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 10 },
  detailLabel: { color: colors.textMuted, fontSize: 12, fontWeight: '600' },
  detailValue: { color: colors.textPrimary, fontSize: 13, textAlign: 'right', flexShrink: 1 },
  mono: { fontFamily: 'monospace', fontSize: 12 },

  notesCard: {
    padding: 14,
    borderRadius: 10,
    backgroundColor: colors.bgSurface,
    borderWidth: 1,
    borderColor: colors.bgLine,
    gap: 6,
  },
  notesLabel: { color: colors.textMuted, fontSize: 11, fontWeight: '700', letterSpacing: 1 },
  notesText: { color: colors.textSecondary, fontSize: 13, lineHeight: 19 },

  integrityCard: {
    padding: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.bgLine,
    backgroundColor: colors.bgDeep,
    gap: 6,
  },
  integrityTitle: { color: colors.caution, fontSize: 12, fontWeight: '700', letterSpacing: 1 },
  integrityText: { color: colors.textMuted, fontSize: 12, lineHeight: 18 },
});
