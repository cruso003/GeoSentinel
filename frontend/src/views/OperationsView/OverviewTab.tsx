import { SiteMap } from '@/components/map/SiteMap';
import { KpiCard } from '@/components/charts/KpiCard';
import { AlertFeed } from '@/components/alerts/AlertFeed';
import { Card } from '@/components/ui/Card';
import { useSensorStore } from '@/store/sensorStore';
import { useAIStore } from '@/store/aiStore';
import { useAlertStore } from '@/store/alertStore';
import { fmtNum } from '@/utils/format';
import { checkCompliance } from '@/utils/ifc-thresholds';
import type { EnvSensorReading } from '@/types';

function trendOf(history: EnvSensorReading[] | undefined, key: keyof EnvSensorReading): 'up' | 'down' | 'flat' {
  if (!history || history.length < 6) return 'flat';
  const a = history[history.length - 6][key] as number | null;
  const b = history[history.length - 1][key] as number | null;
  if (a == null || b == null) return 'flat';
  if (b > a * 1.02) return 'up';
  if (b < a * 0.98) return 'down';
  return 'flat';
}

function spark(history: EnvSensorReading[] | undefined, key: keyof EnvSensorReading) {
  return (history ?? []).slice(-48).map((r) => ({ v: r[key] as number | null }));
}

function tone(check: ReturnType<typeof checkCompliance>): 'good' | 'caution' | 'alert' {
  if (check.exceeded) return 'alert';
  if (check.near_limit) return 'caution';
  return 'good';
}

export function OverviewTab() {
  const env = useSensorStore((s) => s.latestEnvReadings);
  const envHist = useSensorStore((s) => s.envHistory);
  const slopes = useAIStore((s) => s.slopeWatchPredictions);
  const activeAlerts = useAlertStore((s) => s.activeAlerts);

  const env01 = env['ENV-01'];
  const env02 = env['ENV-02'];

  const highestSlope = Object.values(slopes).reduce<number>(
    (acc, s) => (s.risk_score > acc ? s.risk_score : acc),
    0,
  );

  const onlineNodes = Object.values(env).filter((r) => r.ph != null).length;
  const totalNodes = 5;
  const uptime = Math.round((onlineNodes / totalNodes) * 100);

  return (
    <div className="space-y-4 p-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <Card title="Site Map" subtitle="Tokadeh Pilot Site · Nimba County, Liberia">
            <SiteMap height={360} />
          </Card>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <KpiCard
              label="pH (ENV-01)"
              value={fmtNum(env01?.ph, 2)}
              tone={env01 ? tone(checkCompliance('ph', env01.ph)) : 'neutral'}
              trend={trendOf(envHist['ENV-01'], 'ph')}
              spark={spark(envHist['ENV-01'], 'ph')}
            />
            <KpiCard
              label="Turbidity (ENV-01)"
              value={fmtNum(env01?.turbidity, 1)}
              unit="NTU"
              tone={env01 ? tone(checkCompliance('turbidity', env01.turbidity)) : 'neutral'}
              trend={trendOf(envHist['ENV-01'], 'turbidity')}
              spark={spark(envHist['ENV-01'], 'turbidity')}
            />
            <KpiCard
              label="Conductivity (ENV-02)"
              value={fmtNum(env02?.conductivity, 0)}
              unit="µS/cm"
              tone={env02 ? tone(checkCompliance('conductivity', env02.conductivity)) : 'neutral'}
              trend={trendOf(envHist['ENV-02'], 'conductivity')}
              spark={spark(envHist['ENV-02'], 'conductivity')}
            />
            <KpiCard
              label="Highest Slope Risk"
              value={`${Math.round(highestSlope * 100)}`}
              unit="%"
              tone={highestSlope >= 0.7 ? 'alert' : highestSlope >= 0.45 ? 'caution' : 'good'}
              hint={highestSlope >= 0.45 ? 'Investigate' : 'Stable'}
            />
            <KpiCard
              label="Active Alerts"
              value={`${activeAlerts.length}`}
              tone={activeAlerts.length > 0 ? 'caution' : 'good'}
            />
            <KpiCard
              label="Node Uptime"
              value={`${uptime}`}
              unit="%"
              tone={uptime >= 95 ? 'good' : uptime >= 80 ? 'caution' : 'alert'}
            />
          </div>
        </div>

        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-200">Live Alert Feed</h3>
          <AlertFeed limit={30} />
        </div>
      </div>
    </div>
  );
}
