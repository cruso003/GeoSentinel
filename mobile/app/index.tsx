import { Link } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '../src/theme/colors';

interface FeatureCard {
  href: '/where-can-i-mine' | '/receipts' | '/report-concern';
  eyebrow: string;
  title: string;
  description: string;
  cta: string;
  tone: 'green' | 'blue' | 'amber';
}

const FEATURES: FeatureCard[] = [
  {
    href: '/where-can-i-mine',
    eyebrow: '01 · PERMITS',
    title: 'Where can I mine?',
    description:
      'Check your current GPS position against licence boundaries, protected areas, and community forests. Works offline.',
    cta: 'Check my location',
    tone: 'green',
  },
  {
    href: '/receipts',
    eyebrow: '02 · PAYMENTS',
    title: 'Cooperative receipts',
    description:
      'Record daily production and signed receipts for every gold sale. Shareable proof you were paid fairly.',
    cta: 'Open my cooperative',
    tone: 'blue',
  },
  {
    href: '/report-concern',
    eyebrow: '03 · COMMUNITY',
    title: 'Report a concern',
    description:
      'Drop a pin + photo for water, forest, or mining-safety concerns. Reports go straight to EPA & MME.',
    cta: 'Submit a report',
    tone: 'amber',
  },
];

const TONE_ACCENT: Record<FeatureCard['tone'], string> = {
  green: colors.good,
  blue: colors.brand,
  amber: colors.caution,
};

export default function HomeScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bgDeep }} edges={['bottom']}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <Text style={styles.eyebrow}>GeoSentinel · Liberia</Text>
          <Text style={styles.title}>Mining tools you can use today.</Text>
          <Text style={styles.subtitle}>
            For ASM miners, cooperative chairs, and community members in Nimba, Grand Cape Mount,
            Bong, and Gbarpolu. Works offline. No login needed.
          </Text>
        </View>

        {FEATURES.map((card) => (
          <Link key={card.href} href={card.href} asChild>
            <Pressable style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}>
              <View style={styles.cardHeader}>
                <View style={[styles.toneDot, { backgroundColor: TONE_ACCENT[card.tone] }]} />
                <Text style={[styles.cardEyebrow, { color: TONE_ACCENT[card.tone] }]}>
                  {card.eyebrow}
                </Text>
              </View>
              <Text style={styles.cardTitle}>{card.title}</Text>
              <Text style={styles.cardDescription}>{card.description}</Text>
              <Text style={[styles.cardCta, { color: TONE_ACCENT[card.tone] }]}>
                {card.cta} →
              </Text>
            </Pressable>
          </Link>
        ))}

        <View style={styles.footer}>
          <Text style={styles.footerText}>
            Built by four Liberian engineers at the University of Liberia MineTech UniPod, Fendall.
            Open source — your data stays on your phone unless you choose to submit it.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 32,
    gap: 16,
  },
  header: {
    marginBottom: 8,
    gap: 10,
  },
  eyebrow: {
    color: colors.good,
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 2,
    textTransform: 'uppercase',
  },
  title: {
    color: colors.textPrimary,
    fontSize: 30,
    fontWeight: '700',
    lineHeight: 36,
  },
  subtitle: {
    color: colors.textSecondary,
    fontSize: 15,
    lineHeight: 22,
  },
  card: {
    backgroundColor: colors.bgPanel,
    borderRadius: 16,
    padding: 20,
    gap: 10,
    borderWidth: 1,
    borderColor: colors.bgLine,
  },
  cardPressed: {
    opacity: 0.72,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  toneDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  cardEyebrow: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 2,
  },
  cardTitle: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: '600',
  },
  cardDescription: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
  },
  cardCta: {
    fontSize: 14,
    fontWeight: '600',
    marginTop: 6,
  },
  footer: {
    marginTop: 12,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.bgLine,
    backgroundColor: colors.bgDeep,
  },
  footerText: {
    color: colors.textMuted,
    fontSize: 12,
    lineHeight: 18,
  },
});
