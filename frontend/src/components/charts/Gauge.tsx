// Semicircle gauge for exceedance / risk probabilities (0..1).
// Pure SVG to avoid extra deps and keep render cost low.

export function Gauge({
  value,
  label,
  sublabel,
  size = 160,
}: {
  value: number;
  label: string;
  sublabel?: string;
  size?: number;
}) {
  const v = Math.max(0, Math.min(1, value));
  const radius = (size - 16) / 2;
  const cx = size / 2;
  const cy = size - 12;
  const start = polar(cx, cy, radius, 180);
  const end = polar(cx, cy, radius, 180 + 180 * v);
  const fullEnd = polar(cx, cy, radius, 360);

  const color = v >= 0.6 ? '#EF4444' : v >= 0.3 ? '#F59E0B' : '#10B981';
  const largeArc = v > 0.5 ? 1 : 0;

  const trackPath = `M ${start.x} ${start.y} A ${radius} ${radius} 0 1 1 ${fullEnd.x} ${fullEnd.y}`;
  const valuePath = `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 1 ${end.x} ${end.y}`;

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={cy + 6} viewBox={`0 0 ${size} ${cy + 6}`}>
        <path d={trackPath} stroke="#1F3A5F" strokeWidth={10} fill="none" strokeLinecap="round" />
        <path d={valuePath} stroke={color} strokeWidth={10} fill="none" strokeLinecap="round" />
        <text
          x={cx}
          y={cy - 14}
          textAnchor="middle"
          fontSize="22"
          fontWeight="700"
          fill="#F1F5F9"
        >
          {Math.round(v * 100)}%
        </text>
      </svg>
      <div className="-mt-1 text-center">
        <div className="text-xs font-semibold text-slate-200">{label}</div>
        {sublabel && <div className="text-[10px] text-slate-500">{sublabel}</div>}
      </div>
    </div>
  );
}

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}
