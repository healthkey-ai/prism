import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { CohortSeries } from '../../../types'
import { mergeCategorySeries, seriesKey } from '../../../utils/cohortCompare'
import SegmentedToggle from '../../ui/SegmentedToggle'

type Measure = 'diagnoses' | 'treatment_starts'

const MEASURES: { key: Measure; label: string }[] = [
  { key: 'diagnoses', label: 'New Diagnoses' },
  { key: 'treatment_starts', label: 'Treatment Starts' },
]


/** One line per cohort for new diagnoses or treatment starts per quarter. */
export default function IncidenceCompare({ series }: { series: CohortSeries[] }) {
  const [measure, setMeasure] = useState<Measure>('diagnoses')

  const data = useMemo(() => {
    const rows = series.map(s =>
      (s.metrics?.incidence ?? [])
        .filter(d => d.diagnoses > 0 || d.treatment_starts > 0)
        .map(d => ({ name: d.quarter, value: d[measure] })))
    // Quarters are ISO-ish strings ("2021-Q3"); sort so cohorts with different ranges interleave correctly.
    return mergeCategorySeries(rows).sort((a, b) => String(a.name).localeCompare(String(b.name)))
  }, [series, measure])

  if (data.length === 0) {
    return <p className="text-sm text-gray-400 text-center py-6">No incidence data available</p>
  }

  return (
    <div>
      <SegmentedToggle options={MEASURES} value={measure} onChange={setMeasure} />
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-35} textAnchor="end" height={48} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 6 }}
            formatter={(value: unknown, name: unknown) => [String(value), series[Number(String(name).replace('c', ''))]?.label ?? String(name)]}
          />
          <Legend
            wrapperStyle={{ fontSize: 12 }}
            formatter={(value: string) => series[Number(value.replace('c', ''))]?.label ?? value}
          />
          {series.map((s, i) => (
            <Line key={s.key} type="monotone" dataKey={seriesKey(i)} name={seriesKey(i)} stroke={s.color} strokeWidth={2} dot={{ r: 3 }} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
