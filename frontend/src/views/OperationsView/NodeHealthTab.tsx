import { useState } from 'react';
import { Battery, BatteryLow, Signal, X } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Pill } from '@/components/ui/Pill';
import { MOCK_NODES } from '@/mock/site';
import { fmtAgo } from '@/utils/format';
import { useSensorStore } from '@/store/sensorStore';
import { clsx } from '@/utils/clsx';
import type { SensorNode } from '@/types';

const STATUS_TONE: Record<SensorNode['status'], 'good' | 'caution' | 'alert'> = {
  ONLINE: 'good',
  DEGRADED: 'caution',
  OFFLINE: 'alert',
};

export function NodeHealthTab() {
  const env = useSensorStore((s) => s.latestEnvReadings);
  const geo = useSensorStore((s) => s.latestGeoReadings);
  const [selected, setSelected] = useState<SensorNode | null>(null);

  return (
    <div className="space-y-4 p-4">
      <Card title="Node Status Grid" subtitle={`${MOCK_NODES.length} nodes deployed`}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {MOCK_NODES.map((node) => {
            const reading = node.node_type === 'ENVIRONMENTAL' ? env[node.id] : geo[node.id];
            const calDate = new Date(node.calibration_due);
            const calSoon = (calDate.getTime() - Date.now()) / 86400000 < 14;
            const BatteryIcon = node.battery_pct < 25 ? BatteryLow : Battery;
            return (
              <button
                key={node.id}
                type="button"
                onClick={() => setSelected(node)}
                className="gs-card flex flex-col gap-2 p-3 text-left transition hover:border-brand-primary"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-slate-100">{node.id}</div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500">
                      {node.node_type}
                    </div>
                  </div>
                  <Pill tone={STATUS_TONE[node.status]}>{node.status}</Pill>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-400">
                  <span className="flex items-center gap-1">
                    <BatteryIcon className={clsx('h-4 w-4', node.battery_pct < 25 ? 'text-red-400' : 'text-emerald-400')} />
                    {node.battery_pct}%
                  </span>
                  <span className="flex items-center gap-1">
                    <Signal className="h-4 w-4 text-slate-500" />
                    {node.signal_rssi} dBm
                  </span>
                </div>
                <div className="text-[11px] text-slate-500">
                  {reading ? `Last data ${fmtAgo(reading.timestamp)}` : 'Awaiting first packet'}
                </div>
                <div className={clsx('text-[11px]', calSoon ? 'text-amber-300' : 'text-slate-500')}>
                  Calibration due {node.calibration_due}
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {selected && (
        <NodeDetailPanel node={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}

function NodeDetailPanel({ node, onClose }: { node: SensorNode; onClose: () => void }) {
  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full max-w-md overflow-auto border-l border-bg-line bg-bg-panel p-4 shadow-2xl">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h3 className="text-base font-semibold text-white">{node.name}</h3>
          <p className="text-xs text-slate-400">{node.id}</p>
        </div>
        <button type="button" onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-bg-line hover:text-white">
          <X className="h-4 w-4" />
        </button>
      </div>
      <dl className="grid grid-cols-2 gap-2 text-xs">
        <Item k="Status" v={node.status} />
        <Item k="Battery" v={`${node.battery_pct}%`} />
        <Item k="RSSI" v={`${node.signal_rssi} dBm`} />
        <Item k="Lat / Lng" v={`${node.lat.toFixed(4)}, ${node.lng.toFixed(4)}`} />
        <Item k="Elevation" v={`${node.elevation_m} m`} />
        <Item k="Calibration due" v={node.calibration_due} />
      </dl>
      <button type="button" className="gs-button mt-4 w-full justify-center">
        Trigger Calibration Procedure
      </button>
      <p className="mt-3 text-[11px] text-slate-500">
        Calibration history, voltage trend charts, and OTA firmware controls surface
        here when the node reports back over MQTT.
      </p>
    </div>
  );
}

function Item({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded border border-bg-line bg-bg-deep p-2">
      <dt className="text-[10px] uppercase tracking-wider text-slate-500">{k}</dt>
      <dd className="mt-0.5 text-slate-100">{v}</dd>
    </div>
  );
}
