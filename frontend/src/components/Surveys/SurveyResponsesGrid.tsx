import { useMemo } from 'react'
import type { SurveyResponsesData } from '../../api/client'

interface Props {
  data: SurveyResponsesData
}

const COLORS = ['#f1f5f9', '#ccfbf1', '#99f6e4', '#5eead4', '#0f766e', '#115e59']

function cellColor(count: number, maximum: number): string {
  if (count === 0 || maximum === 0) return COLORS[0]
  return COLORS[Math.min(5, Math.ceil((count / maximum) * 5))]
}

export default function SurveyResponsesGrid({ data }: Props) {
  const totalSubmitted = data.total_submitted

  const rows = useMemo(
    () =>
      data.questions.map(q => {
        const maximum = Math.max(0, ...q.options.map(o => o.count))
        return { ...q, maximum }
      }),
    [data.questions]
  )

  if (rows.length === 0) {
    return (
      <p className="text-sm text-gray-500">No categorical questions with responses found.</p>
    )
  }

  return (
    <figure aria-label="Survey responses grid" className="rounded-xl border border-slate-200 bg-slate-50 p-4 sm:p-6 overflow-x-auto">
      <div className="space-y-4">
        {rows.map(q => {
          const rowPct = totalSubmitted > 0 ? Math.round((q.n / totalSubmitted) * 100 * 10) / 10 : 0
          return (
            <div key={q.key} className="flex items-start gap-3">
              {/* Question text */}
              <div className="w-48 shrink-0 flex items-center pt-3">
                <span className="text-xs font-medium text-slate-700 leading-tight">{q.text}</span>
              </div>
              {/* Option cells */}
              <div className="flex flex-wrap gap-1.5 flex-1 min-w-0">
                {q.options.map(opt => {
                  const color = cellColor(opt.count, q.maximum)
                  const isLight = opt.count / (q.maximum || 1) <= 0.6
                  return (
                    <div
                      key={opt.label}
                      role="img"
                      aria-label={`${q.text} — ${opt.label}: ${opt.count} (${opt.pct}%)`}
                      title={`${opt.label}: ${opt.count} respondents (${opt.pct}%)`}
                      className="flex flex-col items-center justify-center rounded-md px-3 py-2 min-w-[90px] tabular-nums transition-transform hover:scale-[1.04]"
                      style={{ backgroundColor: color, color: isLight ? '#134e4a' : '#ffffff' }}
                    >
                      <span className="text-[11px] font-medium leading-tight text-center">{opt.label}</span>
                      <span className="text-base font-bold leading-tight mt-0.5">{opt.count}</span>
                      <span className="text-xs opacity-80">{opt.pct}%</span>
                    </div>
                  )
                })}
              </div>
              {/* Row total */}
              <div className="shrink-0 flex items-center pt-3 text-xs text-slate-500 tabular-nums whitespace-nowrap">
                n={q.n} ({rowPct}%)
              </div>
            </div>
          )
        })}
      </div>
      <figcaption className="mt-4 text-xs text-slate-500">
        % per option = count / question respondents. Row total % = question respondents / total submitted.
      </figcaption>
    </figure>
  )
}
