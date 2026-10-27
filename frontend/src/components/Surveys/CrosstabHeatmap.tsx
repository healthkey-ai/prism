import { useMemo } from 'react'
import type { SurveyCrosstab } from '../../api/client'

interface Props {
  data: SurveyCrosstab
  xQuestion: string
  yQuestion: string
}

const COLORS = ['#f1f5f9', '#ccfbf1', '#99f6e4', '#5eead4', '#0f766e', '#115e59']

function cellColor(count: number, maximum: number): string {
  if (count === 0 || maximum === 0) return COLORS[0]
  return COLORS[Math.min(5, Math.ceil((count / maximum) * 5))]
}

export default function CrosstabHeatmap({ data, xQuestion, yQuestion }: Props) {
  const maximum = useMemo(
    () => Math.max(0, ...data.cells.map(cell => cell.count)),
    [data.cells]
  )
  const cellMap = useMemo(() => {
    const m = new Map<string, Map<string, { count: number; pct: number }>>()
    for (const cell of data.cells) {
      if (!m.has(cell.y)) m.set(cell.y, new Map())
      m.get(cell.y)!.set(cell.x, { count: cell.count, pct: cell.pct })
    }
    return m
  }, [data.cells])

  return <figure aria-label="Crosstabulation heatmap" className="rounded-xl border border-slate-200 bg-slate-50 p-4 sm:p-6">
    <div className="flex gap-3">
      <div className="flex w-8 shrink-0 items-center justify-center">
        <span className="text-center text-xs font-semibold text-slate-700" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
          Y: {yQuestion}
        </span>
      </div>
      <div className="min-w-0 flex-1 overflow-x-auto pb-2">
        <div style={{ minWidth: `${180 + data.x_values.length * 112}px` }}>
          <div className="grid gap-1.5" style={{ gridTemplateColumns: `180px repeat(${data.x_values.length}, minmax(106px, 1fr))` }}>
            {data.y_values.map(row => <div key={row} className="contents">
              <div className="flex items-center justify-end pr-3 text-right text-xs font-medium text-slate-700">{row}</div>
              {data.x_values.map(column => {
                const cell = cellMap.get(row)?.get(column) ?? { count: 0, pct: 0 }
                const color = cellColor(cell.count, maximum)
                return <div
                  key={`${row}:${column}`}
                  role="img"
                  aria-label={`${row} with ${column}: ${cell.count} respondents (${cell.pct}%)`}
                  title={`${row} × ${column}: ${cell.count} respondents (${cell.pct}%)`}
                  className="flex h-16 flex-col items-center justify-center rounded-md tabular-nums transition-transform hover:scale-[1.04]"
                  style={{ backgroundColor: color, color: cell.count / (maximum || 1) > 0.6 ? '#ffffff' : '#134e4a' }}
                >
                  <span className="text-base font-bold leading-tight">{cell.count}</span>
                  <span className="text-xs opacity-80">{cell.pct}%</span>
                </div>
              })}
            </div>)}
            <div aria-hidden="true" />
            {data.x_values.map(column => <div key={column} className="pt-2 text-center text-xs font-medium leading-tight text-slate-700">{column}</div>)}
          </div>
          <div className="ml-[180px] mt-4 text-center text-xs font-semibold text-slate-700">X: {xQuestion}</div>
        </div>
      </div>
    </div>
    <figcaption className="mt-5 flex flex-wrap items-center justify-end gap-2 text-xs text-slate-600">
      <span>n and % of paired respondents per combination</span>
      <span>0</span>
      {COLORS.map((color, index) => <span key={index} aria-hidden="true" className="h-3 w-6 rounded-sm" style={{ backgroundColor: color }} />)}
      <span>{maximum}</span>
      <span className="w-full text-right text-slate-400">* % may exceed 100 for multi-select questions, where one respondent can appear in multiple cells.</span>
    </figcaption>
  </figure>
}
