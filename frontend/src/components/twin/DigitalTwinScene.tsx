import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Sky, Stats } from '@react-three/drei';
import { useState } from 'react';
import { Layers, Eye, EyeOff } from 'lucide-react';
import { MinePit } from './MinePit';
import { SlopeOverlay } from './SlopeOverlay';
import { SensorMarkers } from './SensorMarkers';
import { ExclusionZone } from './ExclusionZone';
import { clsx } from '@/utils/clsx';

const PRESETS = {
  overview: { pos: [120, 90, 120], target: [0, -20, 0] },
  north_wall: { pos: [-40, 50, -120], target: [-40, -20, -40] },
  tailings_dam: { pos: [120, 60, 100], target: [50, -10, 40] },
} as const;

type PresetKey = keyof typeof PRESETS;

export function DigitalTwinScene() {
  const [preset, setPreset] = useState<PresetKey>('overview');
  const [showRisk, setShowRisk] = useState(true);
  const [showNodes, setShowNodes] = useState(true);
  const [showZones, setShowZones] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showWater, setShowWater] = useState(true);

  const cam = PRESETS[preset];

  return (
    <div className="relative h-full w-full">
      <Canvas shadows dpr={[1, 1.6]}>
        <PerspectiveCamera makeDefault position={cam.pos as [number, number, number]} fov={45} />
        <ambientLight intensity={0.55} />
        <directionalLight position={[100, 200, 100]} intensity={1.3} castShadow />
        <Sky distance={800} sunPosition={[100, 80, 100]} inclination={0.5} />
        <MinePit />
        <SlopeOverlay visible={showRisk} />
        <SensorMarkers visible={showNodes} showLabels={showLabels} />
        <ExclusionZone visible={showZones} />
        {showWater && (
          <mesh position={[55, -2, 50]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[60, 50]} />
            <meshStandardMaterial color="#3B82F6" metalness={0.1} roughness={0.2} opacity={0.7} transparent />
          </mesh>
        )}
        <gridHelper args={[400, 40, '#1F3A5F', '#152A47']} position={[0, -50, 0]} />
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
          <ToggleRow label="Risk overlay" value={showRisk} onChange={setShowRisk} />
          <ToggleRow label="Sensor nodes" value={showNodes} onChange={setShowNodes} />
          <ToggleRow label="Exclusion zones" value={showZones} onChange={setShowZones} />
          <ToggleRow label="Labels" value={showLabels} onChange={setShowLabels} />
          <ToggleRow label="Water" value={showWater} onChange={setShowWater} />
        </div>
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
