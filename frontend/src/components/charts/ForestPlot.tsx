import { useMemo } from 'react'
import type { ForestPlotRow } from '../../types'

interface Props {
  data: ForestPlotRow[]
}

const ROW_H    = 36
const PAD_TOP  = 24
const PAD_BOT  = 32
const COL_SUB  = 180  // subgroup + n labels
const COL_PLOT = 260  // visual area
const COL_STAT = 160  // HR (CI) + p-value
const WIDTH    = COL_SUB + COL_PLOT + COL_STAT

// log scale x-axis: 0.1 → 10 mapped onto [0, COL_PLOT]
const LOG_MIN = Math.log(0.1)
const LOG_MAX = Math.log(10)
function xPos(hr: number): number {
  return ((Math.log(hr) - LOG_MIN) / (LOG_MAX - LOG_MIN)) * COL_PLOT
}
const X_ONE = xPos(1.0)  // pixel position of HR = 1

const TICKS = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]

function pLabel(p: number): string {
  if (p < 0.001) return '<0.001'
  if (p < 0.01)  return p.toFixed(3)
  return p.toFixed(2)
}

export default function ForestPlot({ data }: Props) {
  const height = useMemo(
    () => PAD_TOP + data.length * ROW_H + PAD_BOT,
    [data.length]
  )

  if (data.length === 0) {
    return <p className="text-sm text-gray-400 text-center py-6">Insufficient data for subgroup analysis</p>
  }

  return (
    <div className="overflow-x-auto">
      <svg width={WIDTH} height={height} className="font-sans text-xs">
        {/* ── header ───────────────────────────────────────────────── */}
        <text x={0} y={14} fontSize={11} fontWeight={600} fill="#374151">Subgroup</text>
        <text x={COL_SUB + X_ONE - 4} y={14} fontSize={11} fontWeight={600} fill="#374151" textAnchor="middle">HR</text>
        <text x={COL_SUB + COL_PLOT + 4} y={14} fontSize={11} fontWeight={600} fill="#374151">HR (95% CI)</text>
        <text x={WIDTH - 4} y={14} fontSize={11} fontWeight={600} fill="#374151" textAnchor="end">P value</text>

        {/* ── tick marks + axis ────────────────────────────────────── */}
        {TICKS.map(v => {
          const x = COL_SUB + xPos(v)
          return (
            <g key={v}>
              <line x1={x} y1={PAD_TOP - 4} x2={x} y2={PAD_TOP + data.length * ROW_H} stroke="#e5e7eb" strokeWidth={1} />
              <text x={x} y={PAD_TOP + data.length * ROW_H + 12} fontSize={9} fill="#9ca3af" textAnchor="middle">{v}</text>
            </g>
          )
        })}

        {/* HR = 1 reference line */}
        <line
          x1={COL_SUB + X_ONE} y1={PAD_TOP - 4}
          x2={COL_SUB + X_ONE} y2={PAD_TOP + data.length * ROW_H}
          stroke="#6b7280" strokeWidth={1.5} strokeDasharray="4 2"
        />
        <text x={COL_SUB + X_ONE} y={PAD_TOP + data.length * ROW_H + 24} fontSize={9} fill="#6b7280" textAnchor="middle">1.0 (no effect)</text>

        {/* ── rows ─────────────────────────────────────────────────── */}
        {data.map((row, i) => {
          const y     = PAD_TOP + i * ROW_H + ROW_H / 2
          const xHR   = COL_SUB + xPos(row.hr)
          const xLow  = COL_SUB + xPos(Math.max(0.1, row.ci_low))
          const xHigh = COL_SUB + xPos(Math.min(10,  row.ci_high))
          const sig   = row.p_value < 0.05

          return (
            <g key={row.subgroup}>
              {/* row background on hover */}
              <rect x={0} y={y - ROW_H / 2} width={WIDTH} height={ROW_H} fill={i % 2 === 0 ? '#f9fafb' : 'white'} />

              {/* subgroup label */}
              <text x={0} y={y - 4} fontSize={11} fontWeight={600} fill="#111827">{row.subgroup}</text>
              <text x={0} y={y + 8} fontSize={10} fill="#6b7280">
                {row.comparison} (n={row.n_comparison}) vs {row.reference} (n={row.n_reference})
              </text>

              {/* CI whisker line */}
              <line x1={xLow} y1={y} x2={xHigh} y2={y} stroke={sig ? '#2563eb' : '#9ca3af'} strokeWidth={1.5} />
              {/* CI caps */}
              <line x1={xLow}  y1={y - 4} x2={xLow}  y2={y + 4} stroke={sig ? '#2563eb' : '#9ca3af'} strokeWidth={1.5} />
              <line x1={xHigh} y1={y - 4} x2={xHigh} y2={y + 4} stroke={sig ? '#2563eb' : '#9ca3af'} strokeWidth={1.5} />
              {/* HR diamond */}
              <polygon
                points={`${xHR},${y - 6} ${xHR + 6},${y} ${xHR},${y + 6} ${xHR - 6},${y}`}
                fill={sig ? '#2563eb' : '#9ca3af'}
              />

              {/* stat labels */}
              <text x={COL_SUB + COL_PLOT + 6} y={y + 4} fontSize={10} fill={sig ? '#1d4ed8' : '#374151'}>
                {row.hr.toFixed(2)} ({row.ci_low.toFixed(2)}–{row.ci_high.toFixed(2)})
              </text>
              <text x={WIDTH - 4} y={y + 4} fontSize={10} fill={sig ? '#1d4ed8' : '#374151'} textAnchor="end">
                {pLabel(row.p_value)}
              </text>
            </g>
          )
        })}
      </svg>

      {/* legend */}
      <div className="flex items-center gap-6 mt-3 text-xs text-gray-500">
        <div className="flex items-center gap-1.5">
          <svg width={12} height={12}><polygon points="6,0 12,6 6,12 0,6" fill="#2563eb" /></svg>
          Significant (p&lt;0.05)
        </div>
        <div className="flex items-center gap-1.5">
          <svg width={12} height={12}><polygon points="6,0 12,6 6,12 0,6" fill="#9ca3af" /></svg>
          Not significant
        </div>
        <span>HR &lt; 1 = better OS for comparison group</span>
      </div>
    </div>
  )
}
