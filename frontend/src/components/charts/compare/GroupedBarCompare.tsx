import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { CohortSeries } from '../../../types'
import { mergeCategorySeries, seriesKey, type CategoryRow } from '../../../utils/cohortCompare'

interface Props {
  series: CohortSeries[]
  /** One row list per series, in the same order as `series`. */
  rows: CategoryRow[][]
  layout?: 'horizontal' | 'vertical'
  /** Values are percentages (axis 0–100 with % ticks) or raw counts. */
  unit?: 'pct' | 'count'
  height?: number
  /** Width reserved for category labels on a vertical layout. */
  categoryWidth?: number
  emptyMessage?: string
}

/**
 * Grouped bar chart with one bar per cohort for every category.
 * Categories follow the first series' order; extra ones are appended.
 */
export default function GroupedBarCompare({
  series, rows, layout = 'vertical', unit = 'pct', height, categoryWidth = 130,
  emptyMessage = 'No data available',
}: Props) {
  const data = useMemo(() => mergeCategorySeries(rows), [rows])

  if (data.length === 0) {
    return <div className="flex items-center justify-center h-40 text-gray-400 text-sm">{emptyMessage}</div>
  }

  const fmt = (v: unknown) => unit === 'pct' ? `${Number(v).toFixed(1)}%` : String(v)
  const valueAxis = unit === 'pct'
    ? { domain: [0, 100] as [number, number], tickFormatter: (v: number) => `${v}%` }
    : { allowDecimals: false }
  const vertical = layout === 'vertical'
  const h = height ?? (vertical ? Math.max(200, data.length * (14 * series.length + 14)) : 240)

  return (
    <ResponsiveContainer width="100%" height={h}>
      <BarChart
        data={data}
        layout={vertical ? 'vertical' : 'horizontal'}
        margin={{ top: 4, right: 24, left: vertical ? 8 : 0, bottom: vertical ? 4 : 20 }}
        barCategoryGap="20%"
        barGap={2}
      >
        {vertical ? (
          <>
            <XAxis type="number" tick={{ fontSize: 11 }} {...valueAxis} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={categoryWidth} />
          </>
        ) : (
          <>
            <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-35} textAnchor="end" interval={0} height={56} />
            <YAxis tick={{ fontSize: 11 }} {...valueAxis} />
          </>
        )}
        <Tooltip
          contentStyle={{ fontSize: 12 }}
          formatter={(v: unknown, name: unknown) => {
            const idx = Number(String(name).replace('c', ''))
            return [fmt(v), series[idx]?.label ?? String(name)]
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: 11 }}
          formatter={(value: string) => series[Number(value.replace('c', ''))]?.label ?? value}
        />
        {series.map((s, i) => (
          <Bar
            key={s.key}
            dataKey={seriesKey(i)}
            name={seriesKey(i)}
            fill={s.color}
            radius={vertical ? [0, 3, 3, 0] : [3, 3, 0, 0]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
