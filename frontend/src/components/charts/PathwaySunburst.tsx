import { useMemo, useState } from 'react'
import type { MetricsResponse } from '../../types'

type PathwayData = NonNullable<MetricsResponse['pathway_sunburst']>

interface ArcSeg {
  id: string
  name: string
  count: number
  pctOfTotal: number
  pctOfParent: number
  depth: 1 | 2 | 3
  colorIdx: number
  startAngle: number
  endAngle: number
  innerR: number
  outerR: number
}

const PALETTE = [
  '#0d9488', '#0284c7', '#7c3aed', '#db2777',
  '#ea580c', '#16a34a', '#ca8a04', '#0891b2',
  '#dc2626', '#9333ea',
]

const OPACITY: Record<number, number> = { 1: 0.88, 2: 0.60, 3: 0.38 }

const DEPTH_LABEL: Record<number, string> = { 1: '1st Line', 2: '2nd Line', 3: '3rd Line+' }

function polar(cx: number, cy: number, r: number, a: number) {
  return {
    x: cx + r * Math.cos(a - Math.PI / 2),
    y: cy + r * Math.sin(a - Math.PI / 2),
  }
}

function arcPath(
  cx: number, cy: number,
  r0: number, r1: number,
  a0: number, a1: number,
): string {
  // SVG cannot draw a full-circle arc as a single command (start === end point
  // degenerates to nothing). Split into two semicircles when span ≈ 2π.
  if (a1 - a0 >= 2 * Math.PI - 1e-6) {
    const mid = a0 + Math.PI
    return (
      arcPath(cx, cy, r0, r1, a0, mid) +
      ' ' +
      arcPath(cx, cy, r0, r1, mid, a0 + 2 * Math.PI - 1e-4)
    )
  }
  const p1 = polar(cx, cy, r1, a0)
  const p2 = polar(cx, cy, r1, a1)
  const p3 = polar(cx, cy, r0, a1)
  const p4 = polar(cx, cy, r0, a0)
  const lg = a1 - a0 > Math.PI ? 1 : 0
  const f = (n: number) => n.toFixed(2)
  return [
    `M ${f(p1.x)} ${f(p1.y)}`,
    `A ${r1} ${r1} 0 ${lg} 1 ${f(p2.x)} ${f(p2.y)}`,
    `L ${f(p3.x)} ${f(p3.y)}`,
    `A ${r0} ${r0} 0 ${lg} 0 ${f(p4.x)} ${f(p4.y)}`,
    'Z',
  ].join(' ')
}

function buildSegs(
  data: PathwayData,
  cx: number, cy: number,
  R0: number, RW: number,
): ArcSeg[] {
  const segs: ArcSeg[] = []
  const TAU = 2 * Math.PI
  const total = data.total
  let a1 = 0

  const sorted1L = [...data.children].sort((a, b) => b.count - a.count)

  sorted1L.forEach((n1, ci) => {
    const s1 = (n1.count / total) * TAU
    const e1 = a1 + s1
    segs.push({
      id: n1.name,
      name: n1.name,
      count: n1.count,
      pctOfTotal: (n1.count / total) * 100,
      pctOfParent: (n1.count / total) * 100,
      depth: 1,
      colorIdx: ci,
      startAngle: a1,
      endAngle: e1,
      innerR: R0,
      outerR: R0 + RW,
    })

    let a2 = a1
    const sorted2L = [...(n1.children ?? [])].sort((a, b) => b.count - a.count)

    sorted2L.forEach(n2 => {
      const s2 = (n2.count / n1.count) * s1
      const e2 = a2 + s2
      segs.push({
        id: `${n1.name}|${n2.name}`,
        name: n2.name,
        count: n2.count,
        pctOfTotal: (n2.count / total) * 100,
        pctOfParent: (n2.count / n1.count) * 100,
        depth: 2,
        colorIdx: ci,
        startAngle: a2,
        endAngle: e2,
        innerR: R0 + RW,
        outerR: R0 + 2 * RW,
      })

      let a3 = a2
      const sorted3L = [...(n2.children ?? [])].sort((a, b) => b.count - a.count)

      sorted3L.forEach(n3 => {
        const s3 = (n3.count / n2.count) * s2
        const e3 = a3 + s3
        segs.push({
          id: `${n1.name}|${n2.name}|${n3.name}`,
          name: n3.name,
          count: n3.count,
          pctOfTotal: (n3.count / total) * 100,
          pctOfParent: (n3.count / n2.count) * 100,
          depth: 3,
          colorIdx: ci,
          startAngle: a3,
          endAngle: e3,
          innerR: R0 + 2 * RW,
          outerR: R0 + 3 * RW,
        })
        a3 = e3
      })

      a2 = e2
    })

    a1 = e1
  })

  return segs
}

interface Props {
  data: PathwayData
}

export default function PathwaySunburst({ data }: Props) {
  const [hovered, setHovered] = useState<ArcSeg | null>(null)
  const [mouse, setMouse] = useState({ x: 0, y: 0 })

  const SIZE = 460
  const cx = SIZE / 2
  const cy = SIZE / 2
  const R0 = 64
  const RW = 62

  const segs = useMemo(() => buildSegs(data, cx, cy, R0, RW), [data])
  const top1L = useMemo(
    () => [...data.children].sort((a, b) => b.count - a.count).slice(0, 10),
    [data],
  )

  if (!data.total) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
        No treatment data available
      </div>
    )
  }

  return (
    <div className="flex gap-8 items-start">
      {/* SVG */}
      <div className="relative flex-shrink-0">
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          width={SIZE}
          height={SIZE}
          style={{ maxWidth: '100%' }}
        >
          {/* center circle */}
          <circle cx={cx} cy={cy} r={R0 - 3} fill="#f8fafc" stroke="#e2e8f0" strokeWidth={1} />
          <text x={cx} y={cy - 8} textAnchor="middle" fontSize={21} fontWeight="700" fill="#111827">
            {data.total.toLocaleString()}
          </text>
          <text x={cx} y={cy + 10} textAnchor="middle" fontSize={10} fill="#9ca3af">
            patients
          </text>

          {segs.map(seg => {
            const d = arcPath(cx, cy, seg.innerR, seg.outerR, seg.startAngle, seg.endAngle)
            const color = PALETTE[seg.colorIdx % PALETTE.length]
            const isHov = hovered?.id === seg.id
            return (
              <path
                key={seg.id}
                d={d}
                fill={color}
                fillOpacity={isHov ? 1 : OPACITY[seg.depth]}
                stroke="white"
                strokeWidth={0.8}
                style={{ cursor: 'pointer', transition: 'fill-opacity 0.1s' }}
                onMouseEnter={e => { setHovered(seg); setMouse({ x: e.clientX, y: e.clientY }) }}
                onMouseMove={e => setMouse({ x: e.clientX, y: e.clientY })}
                onMouseLeave={() => setHovered(null)}
              />
            )
          })}

          {/* subtle ring-depth labels near 12 o'clock */}
          {([1, 2, 3] as const).map(d => {
            const r = R0 + (d - 0.5) * RW
            const p = polar(cx, cy, r, 0.12)
            return (
              <text
                key={d}
                x={p.x}
                y={p.y}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={9}
                fontWeight="600"
                fill="white"
                fillOpacity={0.85}
                pointerEvents="none"
              >
                {d === 3 ? '3L+' : `${d}L`}
              </text>
            )
          })}
        </svg>

        {/* Tooltip */}
        {hovered && (
          <div
            className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-sm pointer-events-none"
            style={{ left: mouse.x + 14, top: mouse.y - 56 }}
          >
            <div className="font-semibold text-gray-900">{hovered.name}</div>
            <div className="text-xs text-gray-400 mb-1">{DEPTH_LABEL[hovered.depth]}</div>
            <div className="text-gray-700">
              {hovered.count.toLocaleString()} patients &middot; {hovered.pctOfTotal.toFixed(1)}% of cohort
            </div>
            {hovered.depth > 1 && (
              <div className="text-gray-400 text-xs mt-0.5">
                {hovered.pctOfParent.toFixed(1)}% of prior line
              </div>
            )}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="pt-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          1st Line
        </p>
        <div className="space-y-2">
          {top1L.map((n, i) => (
            <div key={n.name} className="flex items-center gap-2">
              <div
                className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                style={{ backgroundColor: PALETTE[i % PALETTE.length] }}
              />
              <span className="text-xs text-gray-700 truncate max-w-[140px]">{n.name}</span>
              <span className="text-xs text-gray-400 ml-auto tabular-nums pl-2">
                {((n.count / data.total) * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
        <div className="mt-5 pt-4 border-t border-gray-100 text-xs text-gray-400 space-y-1">
          <div>Inner ring = 1st line</div>
          <div>Middle ring = 2nd line</div>
          <div>Outer ring = 3rd line+</div>
        </div>
      </div>
    </div>
  )
}
