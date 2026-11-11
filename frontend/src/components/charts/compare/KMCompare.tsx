import { useState } from 'react'
import type { CohortSeries, MetricsResponse, SurvivalLine } from '../../../types'
import KMGroupChart from '../KMGroupChart'

export interface KMOption {
  key: string
  label: string
  pick: (m: MetricsResponse) => SurvivalLine | undefined | null
  xLabel?: string
}

interface Props {
  series: CohortSeries[]
  /** Metrics to choose between (OS/PFS/EFS, 1L/2L…); a single option hides the toggle. */
  options: KMOption[]
  xLabel?: string
  yLabel?: string
  footnote?: React.ReactNode
}

const EMPTY: SurvivalLine = { curve: [], n: 0, median: null }

/** One Kaplan-Meier line per cohort for the selected metric. */
export default function KMCompare({ series, options, xLabel, yLabel, footnote }: Props) {
  const [active, setActive] = useState(options[0]?.key)
  const option = options.find(o => o.key === active) ?? options[0]
  if (!option) return null

  const lines = series.map(s => ({
    label: s.label,
    ...((s.metrics && option.pick(s.metrics)) || EMPTY),
  }))
  const colors = series.map(s => s.color)

  return (
    <div>
      {options.length > 1 && (
        <div className="flex gap-1 rounded-lg border border-gray-200 p-0.5 bg-gray-50 w-fit mb-4">
          {options.map(o => (
            <button
              key={o.key}
              onClick={() => setActive(o.key)}
              className={`px-4 py-1.5 text-xs rounded-md font-semibold transition-colors ${
                o.key === option.key ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
      <KMGroupChart lines={lines} colors={colors} xLabel={option.xLabel ?? xLabel} yLabel={yLabel} />
      {footnote && <p className="text-xs text-gray-400 mt-2">{footnote}</p>}
    </div>
  )
}
