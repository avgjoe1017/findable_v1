'use client'

import { useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { format } from 'date-fns'
import type { Snapshot } from '@/types'

interface TrendChartProps {
  snapshots: Snapshot[]
  height?: number
}

export function TrendChart({ snapshots, height = 300 }: TrendChartProps) {
  const data = useMemo(() => {
    return snapshots
      .slice()
      .reverse()
      .map((snapshot) => ({
        date: snapshot.created_at,
        score: snapshot.score,
        grade: snapshot.grade,
      }))
  }, [snapshots])

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-foreground-muted"
        style={{ height }}
      >
        No data available
      </div>
    )
  }

  const minScore = Math.min(...data.map((d) => d.score))
  const maxScore = Math.max(...data.map((d) => d.score))
  const yMin = Math.max(0, minScore - 10)
  const yMax = Math.min(100, maxScore + 10)

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis
          dataKey="date"
          tickFormatter={(value) => format(new Date(value), 'MMM d')}
          stroke="#64748b"
          fontSize={12}
          tickLine={false}
        />
        <YAxis
          domain={[yMin, yMax]}
          stroke="#64748b"
          fontSize={12}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#0f172a',
            border: '1px solid #334155',
            borderRadius: '8px',
            fontSize: '12px',
          }}
          labelFormatter={(value) => format(new Date(value), 'MMM d, yyyy')}
          formatter={(value: number, name: string) => [
            `${value} (Grade ${data.find((d) => d.score === value)?.grade || '-'})`,
            'Score',
          ]}
        />
        {/* Grade threshold lines */}
        <ReferenceLine y={90} stroke="#22d3ee" strokeDasharray="3 3" strokeOpacity={0.3} />
        <ReferenceLine y={75} stroke="#4ade80" strokeDasharray="3 3" strokeOpacity={0.3} />
        <ReferenceLine y={60} stroke="#fbbf24" strokeDasharray="3 3" strokeOpacity={0.3} />
        <ReferenceLine y={40} stroke="#fb923c" strokeDasharray="3 3" strokeOpacity={0.3} />
        <Line
          type="monotone"
          dataKey="score"
          stroke="#14b8a6"
          strokeWidth={2}
          dot={{ fill: '#14b8a6', strokeWidth: 0, r: 4 }}
          activeDot={{ fill: '#14b8a6', strokeWidth: 2, stroke: '#0f172a', r: 6 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
