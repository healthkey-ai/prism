import type { CohortSeries } from '../../types'

/** Color swatch + label + n for each cohort, shown wherever cohorts are overlaid. */
export default function CohortLegend({ series, className = '' }: { series: CohortSeries[]; className?: string }) {
  return (
    <div className={`flex flex-wrap gap-x-5 gap-y-1 ${className}`}>
      {series.map(s => (
        <div key={s.key} className="flex items-center gap-2 text-xs text-gray-600">
          <span className="inline-block w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: s.color }} />
          <span className="font-semibold truncate max-w-[200px]" title={s.label}>{s.label}</span>
          {s.loading ? (
            <span className="text-gray-400 italic">loading…</span>
          ) : s.metrics ? (
            <span className="text-gray-400 tabular-nums">n={s.metrics.cohort.count.toLocaleString()}</span>
          ) : (
            <span className="text-red-400">unavailable</span>
          )}
        </div>
      ))}
    </div>
  )
}
