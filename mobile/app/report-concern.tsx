import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '../src/theme/colors';

export default function ReportConcernScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bgDeep }} edges={['bottom']}>
      <View style={styles.container}>
        <Text style={styles.title}>Report a concern</Text>
        <Text style={styles.body}>
          Coming next. Drop a pin + photo + two-line description for a water, forest, or safety
          concern. Reports go to EPA + MME + any operator whose concession the pin falls inside.
        </Text>
        <View style={styles.milestone}>
          <Text style={styles.milestoneTag}>Next sprint</Text>
          <Text style={styles.milestoneText}>
            Reuses the community opt-in flow + rate limiting + Ed25519 audit log the backend
            already ships.
          </Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, gap: 16 },
  title: { color: colors.textPrimary, fontSize: 26, fontWeight: '700' },
  body: { color: colors.textSecondary, fontSize: 15, lineHeight: 22 },
  milestone: {
    marginTop: 12,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.bgLine,
    backgroundColor: colors.bgPanel,
    gap: 8,
  },
  milestoneTag: {
    color: colors.caution,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 2,
  },
  milestoneText: { color: colors.textSecondary, fontSize: 13, lineHeight: 19 },
});
