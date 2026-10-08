import type { SurveyCrosstab } from '../../api/client'

type Summary = NonNullable<SurveyCrosstab['numeric_summaries']>[number]
type Group = Summary['groups'][number]

interface Props {
  summaries: Summary[]
  xQuestion: string
  yQuestion: string
}

const ink = '#0f766e'
const grid = '#cbd5e1'
const format = (value: number) => Number(value.toFixed(2)).toString()

function domain(groups: Group[]): [number, number] {
  const values = groups.flatMap(group => [group.mean - (group.sd ?? 0), group.mean + (group.sd ?? 0)])
  if (!values.length) return [0, 1]
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const padding = Math.max((hi - lo) * 0.08, hi === lo ? 1 : 0.1)
  return [lo - padding, hi + padding]
}

function ticks([lo, hi]: [number, number]): number[] {
  return Array.from({ length: 5 }, (_, index) => lo + (hi - lo) * index / 4)
}

function summaryText(group: Group): string {
  return `${group.label}: mean ${format(group.mean)}${group.sd === null ? ', SD unavailable' : `, SD ${format(group.sd)}`}; n=${group.n}`
}

function Horizontal({ groups, xQuestion, yQuestion }: { groups: Group[]; xQuestion: string; yQuestion: string }) {
  const width = 920
  const left = 245
  const right = 180
  const top = 25
  const rowHeight = 58
  const axisY = top + groups.length * rowHeight + 8
  const [lo, hi] = domain(groups)
  const xAt = (value: number) => left + (value - lo) / (hi - lo) * (width - left - right)

  return <svg viewBox={`0 0 ${width} ${axisY + 76}`} className="min-w-[700px] w-full" role="img" aria-label={`Mean ${xQuestion} by ${yQuestion}, with standard deviation bars`}>
    <line x1={left} y1={axisY} x2={width - right} y2={axisY} stroke="#475569" />
    {ticks([lo, hi]).map((tick, index) => <g key={index}>
      <line x1={xAt(tick)} y1={top} x2={xAt(tick)} y2={axisY} stroke={grid} strokeDasharray="3 4" />
      <text x={xAt(tick)} y={axisY + 20} textAnchor="middle" fill="#475569" fontSize="12">{format(tick)}</text>
    </g>)}
    {groups.map((group, index) => {
      const y = top + index * rowHeight + rowHeight / 2
      const spread = group.sd ?? 0
      return <g key={group.label}>
        <title>{summaryText(group)}</title>
        <text x={left - 12} y={y + 4} textAnchor="end" fill="#334155" fontSize="12">
          {group.label.length > 32 ? `${group.label.slice(0, 31)}…` : group.label}
        </text>
        {group.sd !== null && <>
          <line x1={xAt(group.mean - spread)} y1={y} x2={xAt(group.mean + spread)} y2={y} stroke={ink} strokeWidth="3" />
          <line x1={xAt(group.mean - spread)} y1={y - 8} x2={xAt(group.mean - spread)} y2={y + 8} stroke={ink} strokeWidth="2" />
          <line x1={xAt(group.mean + spread)} y1={y - 8} x2={xAt(group.mean + spread)} y2={y + 8} stroke={ink} strokeWidth="2" />
        </>}
        <circle cx={xAt(group.mean)} cy={y} r="6" fill={ink} stroke="white" strokeWidth="2" />
        <text x={width - right + 14} y={y + 4} fill="#334155" fontSize="12">
          {format(group.mean)}{group.sd === null ? ' (n=1)' : ` ± ${format(group.sd)} (n=${group.n})`}
        </text>
      </g>
    })}
    <text x={(left + width - right) / 2} y={axisY + 53} textAnchor="middle" fill="#334155" fontSize="13" fontWeight="600">X: {xQuestion}</text>
    <text transform={`translate(20 ${axisY / 2}) rotate(-90)`} textAnchor="middle" fill="#334155" fontSize="13" fontWeight="600">Y: {yQuestion}</text>
  </svg>
}

function Vertical({ groups, xQuestion, yQuestion }: { groups: Group[]; xQuestion: string; yQuestion: string }) {
  const left = 80
  const top = 30
  const axisY = 250
  const width = Math.max(620, left + groups.length * 150 + 35)
  const [lo, hi] = domain(groups)
  const yAt = (value: number) => axisY - (value - lo) / (hi - lo) * (axisY - top)

  return <svg viewBox={`0 0 ${width} 370`} className="min-w-[620px] w-full" role="img" aria-label={`Mean ${yQuestion} by ${xQuestion}, with standard deviation bars`}>
    <line x1={left} y1={top} x2={left} y2={axisY} stroke="#475569" />
    <line x1={left} y1={axisY} x2={width - 20} y2={axisY} stroke="#475569" />
    {ticks([lo, hi]).map((tick, index) => <g key={index}>
      <line x1={left} y1={yAt(tick)} x2={width - 20} y2={yAt(tick)} stroke={grid} strokeDasharray="3 4" />
      <text x={left - 10} y={yAt(tick) + 4} textAnchor="end" fill="#475569" fontSize="12">{format(tick)}</text>
    </g>)}
    {groups.map((group, index) => {
      const x = left + 75 + index * 150
      const spread = group.sd ?? 0
      return <g key={group.label}>
        <title>{summaryText(group)}</title>
        {group.sd !== null && <>
          <line x1={x} y1={yAt(group.mean - spread)} x2={x} y2={yAt(group.mean + spread)} stroke={ink} strokeWidth="3" />
          <line x1={x - 9} y1={yAt(group.mean - spread)} x2={x + 9} y2={yAt(group.mean - spread)} stroke={ink} strokeWidth="2" />
          <line x1={x - 9} y1={yAt(group.mean + spread)} x2={x + 9} y2={yAt(group.mean + spread)} stroke={ink} strokeWidth="2" />
        </>}
        <circle cx={x} cy={yAt(group.mean)} r="6" fill={ink} stroke="white" strokeWidth="2" />
        <foreignObject x={x - 68} y="262" width="136" height="78">
          <div className="text-center text-xs leading-tight text-slate-700">
            <div className="font-medium">{group.label}</div>
            <div>{format(group.mean)}{group.sd === null ? ' (n=1)' : ` ± ${format(group.sd)} (n=${group.n})`}</div>
          </div>
        </foreignObject>
      </g>
    })}
    <text x={width / 2} y="357" textAnchor="middle" fill="#334155" fontSize="13" fontWeight="600">X: {xQuestion}</text>
    <text transform="translate(18 140) rotate(-90)" textAnchor="middle" fill="#334155" fontSize="13" fontWeight="600">Y: {yQuestion}</text>
  </svg>
}

function Bivariate({ x, y, xQuestion, yQuestion }: { x: Group; y: Group; xQuestion: string; yQuestion: string }) {
  const width = 620
  const height = 390
  const left = 80
  const right = 35
  const top = 25
  const bottom = 65
  const [xLo, xHi] = domain([x])
  const [yLo, yHi] = domain([y])
  const xAt = (value: number) => left + (value - xLo) / (xHi - xLo) * (width - left - right)
  const yAt = (value: number) => height - bottom - (value - yLo) / (yHi - yLo) * (height - bottom - top)

  return <svg viewBox={`0 0 ${width} ${height}`} className="min-w-[560px] w-full" role="img" aria-label={`Mean ${xQuestion} and ${yQuestion}, with standard deviation bars for ${x.n} paired completions`}>
    <line x1={left} y1={top} x2={left} y2={height - bottom} stroke="#475569" />
    <line x1={left} y1={height - bottom} x2={width - right} y2={height - bottom} stroke="#475569" />
    {ticks([xLo, xHi]).map((tick, index) => <g key={`x${index}`}>
      <line x1={xAt(tick)} y1={top} x2={xAt(tick)} y2={height - bottom} stroke={grid} strokeDasharray="3 4" />
      <text x={xAt(tick)} y={height - bottom + 20} textAnchor="middle" fill="#475569" fontSize="12">{format(tick)}</text>
    </g>)}
    {ticks([yLo, yHi]).map((tick, index) => <g key={`y${index}`}>
      <line x1={left} y1={yAt(tick)} x2={width - right} y2={yAt(tick)} stroke={grid} strokeDasharray="3 4" />
      <text x={left - 10} y={yAt(tick) + 4} textAnchor="end" fill="#475569" fontSize="12">{format(tick)}</text>
    </g>)}
    {x.sd !== null && <>
      <line x1={xAt(x.mean - x.sd)} y1={yAt(y.mean)} x2={xAt(x.mean + x.sd)} y2={yAt(y.mean)} stroke={ink} strokeWidth="3" />
      {[x.mean - x.sd, x.mean + x.sd].map((value, index) => <line key={index} x1={xAt(value)} y1={yAt(y.mean) - 8} x2={xAt(value)} y2={yAt(y.mean) + 8} stroke={ink} strokeWidth="2" />)}
    </>}
    {y.sd !== null && <>
      <line x1={xAt(x.mean)} y1={yAt(y.mean - y.sd)} x2={xAt(x.mean)} y2={yAt(y.mean + y.sd)} stroke={ink} strokeWidth="3" />
      {[y.mean - y.sd, y.mean + y.sd].map((value, index) => <line key={index} x1={xAt(x.mean) - 8} y1={yAt(value)} x2={xAt(x.mean) + 8} y2={yAt(value)} stroke={ink} strokeWidth="2" />)}
    </>}
    <circle cx={xAt(x.mean)} cy={yAt(y.mean)} r="7" fill={ink} stroke="white" strokeWidth="2" />
    <text x={width / 2} y={height - 12} textAnchor="middle" fill="#334155" fontSize="13" fontWeight="600">X: {xQuestion}</text>
    <text transform={`translate(18 ${height / 2}) rotate(-90)`} textAnchor="middle" fill="#334155" fontSize="13" fontWeight="600">Y: {yQuestion}</text>
  </svg>
}

export default function NumericSummaryPlot({ summaries, xQuestion, yQuestion }: Props) {
  const x = summaries.find(summary => summary.axis === 'x')
  const y = summaries.find(summary => summary.axis === 'y')
  return <figure aria-label="Numeric survey mean and standard deviation chart" className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-4 sm:p-6">
    {x && y && x.groups[0] && y.groups[0] ?
      <>
        <Bivariate x={x.groups[0]} y={y.groups[0]} xQuestion={xQuestion} yQuestion={yQuestion} />
        <p className="text-center text-xs text-slate-700">
          {x.groups[0].n} paired responses · X mean {format(x.groups[0].mean)}{x.groups[0].sd === null ? '' : ` ± ${format(x.groups[0].sd)}`} · Y mean {format(y.groups[0].mean)}{y.groups[0].sd === null ? '' : ` ± ${format(y.groups[0].sd)}`}
        </p>
      </> :
      x ? <Horizontal groups={x.groups} xQuestion={xQuestion} yQuestion={yQuestion} /> :
      y ? <Vertical groups={y.groups} xQuestion={xQuestion} yQuestion={yQuestion} /> : null}
    <figcaption className="mt-3 text-xs text-slate-600">
      Points show means; bars show ±1 sample standard deviation. A group with one response has no standard deviation bar. Sample sizes are shown beside each group or in the chart label.
    </figcaption>
  </figure>
}
