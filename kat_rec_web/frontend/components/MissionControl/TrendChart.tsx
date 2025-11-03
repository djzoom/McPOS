'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

interface TrendChartProps {
  data: Array<{ date: string; value: number }>
  title: string
}

export function TrendChart({ data, title }: TrendChartProps) {
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis
            dataKey="date"
            stroke="#888"
            tick={{ fill: '#888', fontSize: 12 }}
            tickFormatter={(value) => {
              const date = new Date(value)
              return `${date.getMonth() + 1}/${date.getDate()}`
            }}
          />
          <YAxis stroke="#888" tick={{ fill: '#888', fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: '#2a2a2a',
              border: '1px solid #333',
              borderRadius: '8px',
              color: '#e0e0e0',
            }}
            labelFormatter={(value) => {
              const date = new Date(value)
              return date.toLocaleDateString('zh-CN')
            }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#4a9eff"
            strokeWidth={2}
            dot={{ fill: '#4a9eff', r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

