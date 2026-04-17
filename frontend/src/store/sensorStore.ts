import { create } from 'zustand';
import type { EnvSensorReading, GeoSensorReading } from '@/types';

const HISTORY_CAP = 1440; // ~24h @ 1min cadence

interface SensorState {
  latestEnvReadings: Record<string, EnvSensorReading>;
  latestGeoReadings: Record<string, GeoSensorReading>;
  envHistory: Record<string, EnvSensorReading[]>;
  geoHistory: Record<string, GeoSensorReading[]>;
  setLatestEnvReading: (reading: EnvSensorReading) => void;
  setLatestGeoReading: (reading: GeoSensorReading) => void;
  hydrateEnvHistory: (nodeId: string, readings: EnvSensorReading[]) => void;
  hydrateGeoHistory: (nodeId: string, readings: GeoSensorReading[]) => void;
  appendEnvHistory: (nodeId: string, reading: EnvSensorReading) => void;
  appendGeoHistory: (nodeId: string, reading: GeoSensorReading) => void;
  reset: () => void;
}

const initial = {
  latestEnvReadings: {},
  latestGeoReadings: {},
  envHistory: {},
  geoHistory: {},
};

export const useSensorStore = create<SensorState>((set) => ({
  ...initial,
  setLatestEnvReading: (reading) =>
    set((s) => ({
      latestEnvReadings: { ...s.latestEnvReadings, [reading.node_id]: reading },
    })),
  setLatestGeoReading: (reading) =>
    set((s) => ({
      latestGeoReadings: { ...s.latestGeoReadings, [reading.node_id]: reading },
    })),
  hydrateEnvHistory: (nodeId, readings) =>
    set((s) => ({ envHistory: { ...s.envHistory, [nodeId]: readings.slice(-HISTORY_CAP) } })),
  hydrateGeoHistory: (nodeId, readings) =>
    set((s) => ({ geoHistory: { ...s.geoHistory, [nodeId]: readings.slice(-HISTORY_CAP) } })),
  appendEnvHistory: (nodeId, reading) =>
    set((s) => {
      const next = [...(s.envHistory[nodeId] ?? []), reading];
      if (next.length > HISTORY_CAP) next.splice(0, next.length - HISTORY_CAP);
      return { envHistory: { ...s.envHistory, [nodeId]: next } };
    }),
  appendGeoHistory: (nodeId, reading) =>
    set((s) => {
      const next = [...(s.geoHistory[nodeId] ?? []), reading];
      if (next.length > HISTORY_CAP) next.splice(0, next.length - HISTORY_CAP);
      return { geoHistory: { ...s.geoHistory, [nodeId]: next } };
    }),
  reset: () => set(initial),
}));
