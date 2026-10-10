import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Sky, Stats } from '@react-three/drei';
import { useState } from 'react';
import { Layers, Eye, EyeOff } from 'lucide-react';
import { NimbaTerrain } from './NimbaTerrain';
import { SensorMarkers } from './SensorMarkers';
import type { Dem } from './terrain';
import { clsx } from '@/utils/clsx';

const PRESETS = {
  overview: { pos: [-80, 60, 110], target: [0, 8, 0] },
  mount_nimba: { pos: [40, 30, 90], target: [50, 14, -40] },
  yekepa: { pos: [-30, 20, 30], target: [-20, 5, 20] },
} as const;

type PresetKey = keyof typeof PRESETS;

export function DigitalTwinScene() {
  const [preset, setPreset] = useState<PresetKey>('overview');
  const [showNodes, setShowNodes] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [dem, setDem] = useState<Dem | null>(null);

  const cam = PRESETS[preset];

  return (
    <div className="relative h-full w-full">
      <Canvas shadows dpr={[1, 1.6]}>
        <PerspectiveCamera makeDefault position={cam.pos as [number, number, number]} fov={45} />
        <ambientLight intensity={0.55} />
        <directionalLight position={[-120, 180, 60]} intensity={1.1} castShadow />
        <Sky distance={800} sunPosition={[-120, 180, 60]} inclination={0.5} />
        <NimbaTerrain onLoad={setDem} />
        <SensorMarkers dem={dem} visible={showNodes} showLabels={showLabels} />
        <OrbitControls makeDefault target={cam.target as [number, number, number]} />
        {import.meta.env.DEV && false && <Stats />}
      </Canvas>

      <div className="absolute right-3 top-3 flex flex-col gap-2">
        <div className="gs-card flex flex-col gap-1 p-2 text-[11px]">
          <div className="px-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Camera
          </div>
          {(Object.keys(PRESETS) as PresetKey[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setPreset(k)}
              className={clsx(
                'rounded px-2 py-1 text-left transition',
                preset === k ? 'bg-brand-primary text-white' : 'text-slate-300 hover:bg-bg-line',
              )}
            >
              {k.replace('_', ' ')}
            </button>
          ))}
        </div>
        <div className="gs-card flex flex-col gap-1 p-2 text-[11px]">
          <div className="flex items-center gap-1 px-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            <Layers className="h-3 w-3" /> Overlays
          </div>
          <ToggleRow label="Sensor nodes" value={showNodes} onChange={setShowNodes} />
          <ToggleRow label="Labels" value={showLabels} onChange={setShowLabels} />
        </div>
      </div>

      {/* Terrain attribution — Copernicus GLO-30 licence requires it. */}
      <div className="absolute bottom-3 left-3 rounded bg-bg-deep/80 px-2 py-1 text-[10px] text-slate-400 ring-1 ring-bg-line">
        {dem ? (
          <>
            Terrain: Contains modified <b>Copernicus GLO-30</b> data (ESA).
            Area: {dem.extent_m.width.toFixed(0)} m &times; {dem.extent_m.height.toFixed(0)} m.
            Elevation: {dem.elevation_m.min.toFixed(0)}&ndash;{dem.elevation_m.max.toFixed(0)} m.
            Pit geometry pending operator sharing.
          </>
        ) : (
          <>Loading Nimba terrain&hellip;</>
        )}
      </div>
    </div>
  );
}

function ToggleRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className="flex items-center justify-between gap-3 rounded px-2 py-1 hover:bg-bg-line"
    >
      <span className="text-slate-300">{label}</span>
      {value ? <Eye className="h-3 w-3 text-emerald-400" /> : <EyeOff className="h-3 w-3 text-slate-500" />}
    </button>
  );
}
