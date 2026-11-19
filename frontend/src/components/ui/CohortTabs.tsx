import { useState, type ReactNode } from 'react'
import type { CohortSeries } from '../../types'

interface Props {
  series: CohortSeries[]
  /** Render the chart for the selected cohort; `null` metrics means it is still loading or failed. */
  children: (cohort: CohortSeries) => ReactNode
}

/**
 * One tab per cohort for charts that cannot overlay several cohorts
 * (Sankey, sunburst, tables, multi-panel cards).
 */
export default function CohortTabs({ series, children }: Props) {
  // Keyed by cohort, not index, so removing another cohort keeps this one selected.
  const [selectedKey, setSelectedKey] = useState(series[0]?.key)
  const found = series.findIndex(s => s.key === selectedKey)
  const idx = found >= 0 ? found : 0
  const current = series[idx]
  if (!current) return null

  return (
    <div>
      <div role="tablist" className="flex flex-wrap gap-1 rounded-lg border border-gray-200 p-0.5 bg-gray-50 w-fit mb-4">
        {series.map((s, i) => (
          <button
            key={s.key}
            role="tab"
            aria-selected={i === idx}
            onClick={() => setSelectedKey(s.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md font-semibold transition-colors ${
              i === idx ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: s.color }} />
            <span className="max-w-[160px] truncate">{s.label}</span>
            {s.metrics && (
              <span className="text-gray-400 font-normal tabular-nums">n={s.metrics.cohort.count.toLocaleString()}</span>
            )}
          </button>
        ))}
      </div>
      {current.loading ? (
        <div className="flex items-center justify-center h-32 text-gray-400 text-sm">Loading…</div>
      ) : (
        children(current)
      )}
    </div>
  )
}
