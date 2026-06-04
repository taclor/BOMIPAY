'use client'

import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'

interface SparklineProps {
  data: { value: number; timestamp?: string }[]
  color?: string
  height?: number
}

export default function Sparkline({ data, color = '#3b82f6', height = 40 }: SparklineProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
        <Tooltip
          contentStyle={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 4, fontSize: 10 }}
          labelStyle={{ display: 'none' }}
          itemStyle={{ color: '#f9fafb' }}
          formatter={(v) => [Number(v).toFixed(0), '']}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
