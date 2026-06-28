import { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { MetricsResponse } from '../../types'

type Data = NonNullable<MetricsResponse['incidence']>

interface Props { data: Data }

export default function IncidenceChart({ data }: Props) {
  const filtered = useMemo(() => data.filter(d => d.diagnoses > 0 || d.treatment_starts > 0), [data])

  if (filtered.length === 0) {
    return <p className="text-sm text-gray-400 text-center py-6">No incidence data available</p>
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={filtered} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="quarter"
          tick={{ fontSize: 11 }}
          angle={-35}
          textAnchor="end"
          height={48}
          interval="preserveStartEnd"
        />
        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
        <Tooltip
          contentStyle={{ fontSize: 12, borderRadius: 6 }}
          formatter={(value, name) => [
            value,
            name === 'diagnoses' ? 'New diagnoses' : 'Treatment starts',
          ]}
        />
        <Legend
          formatter={(value) => value === 'diagnoses' ? 'New Diagnoses' : 'Treatment Starts'}
          wrapperStyle={{ fontSize: 12 }}
        />
        <Line type="monotone" dataKey="diagnoses"        stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
        <Line type="monotone" dataKey="treatment_starts" stroke="#16a34a" strokeWidth={2} dot={{ r: 3 }} strokeDasharray="4 2" />
      </LineChart>
    </ResponsiveContainer>
  )
}
