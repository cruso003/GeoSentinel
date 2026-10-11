import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { colors } from '../src/theme/colors';

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.bgDeep }}>
      <SafeAreaProvider>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: colors.bgDeep },
            headerTintColor: colors.textPrimary,
            headerTitleStyle: { fontWeight: '600' },
            contentStyle: { backgroundColor: colors.bgDeep },
          }}
        >
          <Stack.Screen name="index" options={{ title: 'GeoSentinel' }} />
          <Stack.Screen name="where-can-i-mine" options={{ title: 'Where can I mine?' }} />
          <Stack.Screen name="report-concern" options={{ title: 'Report a concern' }} />
          <Stack.Screen name="receipts" options={{ title: 'Cooperative receipts' }} />
        </Stack>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
