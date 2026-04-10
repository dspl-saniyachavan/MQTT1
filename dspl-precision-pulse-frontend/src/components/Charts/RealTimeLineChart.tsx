'use client';

import { useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';

interface DataPoint {
  timestamp: string;
  value: number;
  parameter_name: string;
  unit?: string;
}

interface RealTimeLineChartProps {
  title?: string;
  data: DataPoint[];
  parameterId?: string;
  unit?: string;
  minValue?: number;
  maxValue?: number;
  height?: number;
  showLegend?: boolean;
  showGrid?: boolean;
  animationDuration?: number;
}

export default function RealTimeLineChart({
  title = 'Real-time Data',
  data = [],
  parameterId,
  unit = '',
  minValue,
  maxValue,
  height = 400,
  showLegend = true,
  showGrid = true,
  animationDuration = 300
}: RealTimeLineChartProps) {
  const [chartData, setChartData] = useState<any[]>([]);
  const [stats, setStats] = useState({
    current: 0,
    min: 0,
    max: 0,
    avg: 0
  });

  useEffect(() => {
    if (data && data.length > 0) {
      const transformedData = data.map((point, index) => ({
        time: new Date(point.timestamp).toLocaleTimeString(),
        value: point.value,
        timestamp: point.timestamp,
        fullTime: new Date(point.timestamp).toLocaleString()
      }));

      setChartData(transformedData);

      const values = data.map(d => d.value);
      const current = values[values.length - 1] || 0;
      const min = Math.min(...values);
      const max = Math.max(...values);
      const avg = values.reduce((a, b) => a + b, 0) / values.length;

      setStats({ current, min, max, avg });
    }
  }, [data]);

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 shadow-lg">
          <p className="text-white font-semibold">{payload[0].payload.fullTime}</p>
          <p className="text-indigo-400">
            Value: {payload[0].value.toFixed(2)} {unit}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full bg-slate-800/50 border border-slate-700 rounded-lg p-6">
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
        
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-slate-700/50 rounded-lg p-3">
            <p className="text-slate-400 text-xs font-medium">Current</p>
            <p className="text-white text-lg font-bold">
              {stats.current.toFixed(2)} {unit}
            </p>
          </div>
          <div className="bg-slate-700/50 rounded-lg p-3">
            <p className="text-slate-400 text-xs font-medium">Min</p>
            <p className="text-blue-400 text-lg font-bold">
              {stats.min.toFixed(2)} {unit}
            </p>
          </div>
          <div className="bg-slate-700/50 rounded-lg p-3">
            <p className="text-slate-400 text-xs font-medium">Max</p>
            <p className="text-red-400 text-lg font-bold">
              {stats.max.toFixed(2)} {unit}
            </p>
          </div>
          <div className="bg-slate-700/50 rounded-lg p-3">
            <p className="text-slate-400 text-xs font-medium">Average</p>
            <p className="text-green-400 text-lg font-bold">
              {stats.avg.toFixed(2)} {unit}
            </p>
          </div>
        </div>
      </div>

      {chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            {showGrid && (
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            )}
            <XAxis
              dataKey="time"
              stroke="#94a3b8"
              style={{ fontSize: '12px' }}
            />
            <YAxis
              stroke="#94a3b8"
              style={{ fontSize: '12px' }}
              domain={[minValue || 'auto', maxValue || 'auto']}
            />
            <Tooltip content={<CustomTooltip />} />
            {showLegend && <Legend />}
            
            {minValue && (
              <ReferenceLine
                y={minValue}
                stroke="#ef4444"
                strokeDasharray="5 5"
                label={{ value: `Min: ${minValue}`, position: 'right', fill: '#ef4444' }}
              />
            )}
            {maxValue && (
              <ReferenceLine
                y={maxValue}
                stroke="#22c55e"
                strokeDasharray="5 5"
                label={{ value: `Max: ${maxValue}`, position: 'right', fill: '#22c55e' }}
              />
            )}
            
            <Line
              type="monotone"
              dataKey="value"
              stroke="#6366f1"
              dot={false}
              isAnimationActive={true}
              animationDuration={animationDuration}
              strokeWidth={2}
              name={`Value (${unit})`}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="h-96 flex items-center justify-center">
          <p className="text-slate-400">No data available</p>
        </div>
      )}

      <div className="mt-4 text-xs text-slate-400">
        Showing {chartData.length} data points
      </div>
    </div>
  );
}
