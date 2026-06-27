import { useMemo, useState } from 'react'
import type { PathwayNode } from '../../types'

interface Props {
  data: PathwayNode
}

interface ArcSlice {
  d: string
  name: string
  value: number
  depth: number
  color: string
}

const RING_COLORS: Record<number, string[]> = {
  1: ['#0d9488', '#0f766e', '#2dd4bf', '#0891b2', '#14b8a6', '#0369a1', '#134e4a'],
  2: ['#2563eb', '#1d4ed8', '#3b82f6', '#0284c7', '#1e40af', '#60a5fa', '#0369a1'],
  3: ['#7c3aed', '#6d28d9', '#8b5cf6', '#9333ea', '#a78bfa', '#5b21b6', '#7e22ce'],
}
const STOPPED_COLOR = '#9ca3af'
const INNER_R = 45
const RING_W = 68
const CX = 250
const CY = 250

function nodeValue(node: PathwayNode): number {
  if (node.value !== undefined) return node.value
  return (node.children ?? []).reduce((s, c) => s + nodeValue(c), 0)
}

function polar(cx: number, cy: number, r: number, angle: number) {
  return {
    x: cx + r * Math.cos(angle - Math.PI / 2),
    y: cy + r * Math.sin(angle - Math.PI / 2),
  }
}

function makeArc(
  cx: number,
  cy: number,
  innerR: number,
  outerR: number,
  start: number,
  end: number
): string {
  const p1 = polar(cx, cy, outerR, start)
  const p2 = polar(cx, cy, outerR, end)
  const p3 = polar(cx, cy, innerR, end)
  const p4 = polar(cx, cy, innerR, start)
  const large = end - start > Math.PI ? 1 : 0
  return [
    `M ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`,
    `A ${outerR} ${outerR} 0 ${large} 1 ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`,
    `L ${p3.x.toFixed(2)} ${p3.y.toFixed(2)}`,
    `A ${innerR} ${innerR} 0 ${large} 0 ${p4.x.toFixed(2)} ${p4.y.toFixed(2)}`,
    'Z',
  ].join(' ')
}

function collectSlices(
  node: PathwayNode,
  depth: number,
  startAngle: number,
  endAngle: number,
  siblingIdx: number,
  slices: ArcSlice[]
) {
  if (depth === 0) {
    const total = nodeValue(node)
    if (total === 0) return
    let a = startAngle
    ;(node.children ?? []).forEach((child, i) => {
      const v = nodeValue(child)
      const childEnd = a + (endAngle - startAngle) * (v / total)
      collectSlices(child, 1, a, childEnd, i, slices)
      a = childEnd
    })
    return
  }

  const span = endAngle - startAngle
  if (span < 0.003) return

  const innerR = INNER_R + (depth - 1) * RING_W
  const outerR = INNER_R + depth * RING_W

  let color: string
  if (node.name === '—') {
    color = STOPPED_COLOR
  } else {
    const palette = RING_COLORS[depth] ?? RING_COLORS[1]
    color = palette[siblingIdx % palette.length]
  }

  slices.push({
    d: makeArc(CX, CY, innerR, outerR, startAngle, endAngle),
    name: node.name,
    value: nodeValue(node),
    depth,
    color,
  })

  if (node.children?.length) {
    const total = nodeValue(node)
    if (total > 0) {
      let a = startAngle
      node.children.forEach((child, i) => {
        const v = nodeValue(child)
        const childEnd = a + span * (v / total)
        collectSlices(child, depth + 1, a, childEnd, i, slices)
        a = childEnd
      })
    }
  }
}

const DEPTH_LABELS = ['', '1st Line', '2nd Line', '3rd Line+']

export default function TreatmentPathwaysSunburst({ data }: Props) {
  const [tooltip, setTooltip] = useState<{
    name: string
    value: number
    depth: number
    x: number
    y: number
  } | null>(null)

  const slices = useMemo(() => {
    const result: ArcSlice[] = []
    collectSlices(data, 0, 0, 2 * Math.PI, 0, result)
    return result
  }, [data])

  const totalValue = nodeValue(data)

  if (slices.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
        No data available
      </div>
    )
  }

  return (
    <div>
      <div className="relative flex justify-center">
        <svg
          width={500}
          height={500}
          onMouseLeave={() => setTooltip(null)}
          style={{ overflow: 'visible' }}
        >
          {slices.map((slice, i) => (
            <path
              key={i}
              d={slice.d}
              fill={slice.color}
              stroke="white"
              strokeWidth={1.5}
              style={{ cursor: 'pointer' }}
              onMouseEnter={(e) => {
                const rect = (e.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect()
                setTooltip({
                  name: slice.name,
                  value: slice.value,
                  depth: slice.depth,
                  x: e.clientX - rect.left,
                  y: e.clientY - rect.top,
                })
              }}
              onMouseMove={(e) => {
                const rect = (e.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect()
                setTooltip(prev => prev
                  ? { ...prev, x: e.clientX - rect.left, y: e.clientY - rect.top }
                  : null
                )
              }}
            />
          ))}

          {/* Center label */}
          <text x={CX} y={CY - 8} textAnchor="middle" fontSize={16} fontWeight="600" fill="#111827">
            {totalValue.toLocaleString()}
          </text>
          <text x={CX} y={CY + 12} textAnchor="middle" fontSize={11} fill="#6b7280">
            patients
          </text>

          {/* SVG tooltip */}
          {tooltip && (() => {
            const label = tooltip.name === '—' ? 'Discontinued' : tooltip.name
            const boxW = Math.max(label.length * 7 + 20, 140)
            const tx = Math.min(tooltip.x + 12, 500 - boxW - 4)
            const ty = Math.max(tooltip.y - 36, 4)
            return (
              <g transform={`translate(${tx}, ${ty})`} style={{ pointerEvents: 'none' }}>
                <rect x={0} y={0} width={boxW} height={46} rx={4} fill="white" stroke="#e5e7eb" strokeWidth={1} />
                <text x={8} y={17} fontSize={11} fontWeight="600" fill="#111827">{label}</text>
                <text x={8} y={34} fontSize={11} fill="#6b7280">
                  {tooltip.value.toLocaleString()} pts · {DEPTH_LABELS[tooltip.depth]}
                </text>
              </g>
            )
          })()}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex justify-center flex-wrap gap-5 mt-1">
        {[1, 2, 3].map((depth) => (
          <div key={depth} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: RING_COLORS[depth][0] }} />
            <span className="text-xs text-gray-500">{DEPTH_LABELS[depth]}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: STOPPED_COLOR }} />
          <span className="text-xs text-gray-500">Discontinued</span>
        </div>
      </div>
      <p className="text-xs text-gray-400 text-center mt-2">
        Each ring represents a line of therapy. Arc width = proportion of patients. Gray = discontinued at that line.
      </p>
    </div>
  )
}
