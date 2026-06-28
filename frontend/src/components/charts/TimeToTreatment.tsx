import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { MetricsResponse } from '../../types'

type Data = NonNullable<MetricsResponse['time_to_treatment']>

interface Props { data: Data }

const COLORS = ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444', '#991b1b']

export default function TimeToTreatment({ data }: Props) {
  if (!data.histogram.length || data.n === 0) {
    return <p className="text-sm text-gray-400 text-center py-6">No time-to-treatment data available</p>
  }

  return (
    <div>
      {data.median_days != null && (
        <p className="text-sm text-gray-600 mb-3">
          Median time to first treatment: <span className="font-semibold text-gray-900">{data.median_days} days</span>
          <span className="text-gray-400 ml-2">(n = {data.n})</span>
        </p>
      )}
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data.histogram} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 6 }}
            formatter={(value) => [value, 'Patients']}
          />
          <Bar dataKey="count" radius={[3, 3, 0, 0]}>
            {data.histogram.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="text-xs text-gray-400 mt-1 text-center">Days from diagnosis to first treatment</p>
    </div>
  )
}
