import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { format, parseISO } from 'date-fns';

const COLORS = ['#22D3EE', '#A78BFA', '#FB923C', '#34D399', '#F472B6'];

export interface SeriesPoint {
  t: string;
  [key: string]: number | string | null;
}

export function TimeSeriesChart({
  data,
  series,
  unit,
  thresholdMax,
  thresholdMin,
  height = 280,
}: {
  data: SeriesPoint[];
  series: string[];
  unit?: string;
  thresholdMax?: number;
  thresholdMin?: number;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#1F3A5F" strokeDasharray="3 3" />
        <XAxis
          dataKey="t"
          stroke="#64748B"
          fontSize={11}
          tickFormatter={(v) => {
            try {
              return format(parseISO(v as string), 'HH:mm');
            } catch {
              return v as string;
            }
          }}
          minTickGap={32}
        />
        <YAxis
          stroke="#64748B"
          fontSize={11}
          width={48}
          label={
            unit
              ? { value: unit, angle: -90, position: 'insideLeft', fill: '#64748B', fontSize: 10 }
              : undefined
          }
        />
        <Tooltip
          contentStyle={{
            background: '#0F1F36',
            border: '1px solid #1F3A5F',
            borderRadius: 8,
            color: '#F1F5F9',
            fontSize: 12,
          }}
          labelFormatter={(v) => format(parseISO(v as string), 'MMM d HH:mm')}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: '#94A3B8' }} />
        {thresholdMax !== undefined && (
          <ReferenceLine
            y={thresholdMax}
            stroke="#EF4444"
            strokeDasharray="4 4"
            label={{ value: `IFC max ${thresholdMax}`, fill: '#EF4444', fontSize: 10, position: 'right' }}
          />
        )}
        {thresholdMin !== undefined && (
          <ReferenceLine
            y={thresholdMin}
            stroke="#EF4444"
            strokeDasharray="4 4"
            label={{ value: `IFC min ${thresholdMin}`, fill: '#EF4444', fontSize: 10, position: 'right' }}
          />
        )}
        {series.map((k, i) => (
          <Line
            key={k}
            type="monotone"
            dataKey={k}
            stroke={COLORS[i % COLORS.length]}
            strokeWidth={1.6}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
