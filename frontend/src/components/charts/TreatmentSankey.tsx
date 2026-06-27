import { useMemo, useState } from 'react'
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore – d3-sankey ships CJS; types are in @types/d3-sankey
import { sankey, sankeyLeft, sankeyLinkHorizontal } from 'd3-sankey'
import type { MetricsResponse } from '../../types'

type SwitchingData = NonNullable<MetricsResponse['switching']>

interface Props {
  data: SwitchingData
}

interface SNode {
  id: string
  label: string
  lineLevel: 1 | 2 | 3
  // populated by d3-sankey:
  x0?: number
  x1?: number
  y0?: number
  y1?: number
  value?: number
}

interface SLink {
  source: string | SNode
  target: string | SNode
  value: number
  fromLabel: string
  toLabel: string
  n: number
  pct: number
  // populated by d3-sankey:
  y0?: number
  y1?: number
  width?: number
}

const LEVEL_COLORS: Record<number, string> = {
  1: '#0d9488',
  2: '#2563eb',
  3: '#7c3aed',
}

const WIDTH = 580
const HEIGHT = 380
const PAD = { top: 8, right: 120, bottom: 8, left: 8 }

function shorten(name: string, max = 16): string {
  return name.length > max ? name.slice(0, max - 1) + '…' : name
}

export default function TreatmentSankey({ data }: Props) {
  const [hoveredLink, setHoveredLink] = useState<SLink | null>(null)

  const { nodes, links } = useMemo(() => {
    const nodeMap = new Map<string, SNode>()
    const linkList: SLink[] = []

    function getOrCreate(id: string, label: string, level: 1 | 2 | 3): SNode {
      if (!nodeMap.has(id)) nodeMap.set(id, { id, label, lineLevel: level })
      return nodeMap.get(id)!
    }

    // 1L → 2L
    for (const row of data.from_1l ?? []) {
      getOrCreate(`1L:${row.from_regimen}`, row.from_regimen, 1)
      for (const sw of row.switches) {
        getOrCreate(`2L:${sw.to_regimen}`, sw.to_regimen, 2)
        linkList.push({
          source: `1L:${row.from_regimen}`,
          target: `2L:${sw.to_regimen}`,
          value: sw.n,
          fromLabel: row.from_regimen,
          toLabel: sw.to_regimen,
          n: sw.n,
          pct: sw.pct,
        })
      }
    }

    // 2L → 3L
    for (const row of data.from_2l ?? []) {
      getOrCreate(`2L:${row.from_regimen}`, row.from_regimen, 2)
      for (const sw of row.switches) {
        getOrCreate(`3L:${sw.to_regimen}`, sw.to_regimen, 3)
        linkList.push({
          source: `2L:${row.from_regimen}`,
          target: `3L:${sw.to_regimen}`,
          value: sw.n,
          fromLabel: row.from_regimen,
          toLabel: sw.to_regimen,
          n: sw.n,
          pct: sw.pct,
        })
      }
    }

    const nodeArray = Array.from(nodeMap.values())
    if (nodeArray.length === 0 || linkList.length === 0) {
      return { nodes: [] as SNode[], links: [] as SLink[] }
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sankeyGen = (sankey as any)()
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .nodeId((d: any) => d.id)
      .nodeAlign(sankeyLeft)
      .nodeWidth(14)
      .nodePadding(10)
      .extent([[PAD.left, PAD.top], [WIDTH - PAD.right, HEIGHT - PAD.bottom]])

    const graph = sankeyGen({ nodes: nodeArray, links: linkList })
    return graph as { nodes: SNode[]; links: SLink[] }
  }, [data])

  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
        No switching data available
      </div>
    )
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pathGen = (sankeyLinkHorizontal as any)()

  return (
    <div>
      <svg width={WIDTH} height={HEIGHT} style={{ overflow: 'visible' }}>
        {/* Links */}
        {(links as SLink[]).map((link, i) => {
          const srcNode = link.source as SNode
          const color = LEVEL_COLORS[srcNode.lineLevel] ?? '#9ca3af'
          const isHov = hoveredLink === link
          return (
            <path
              key={i}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              d={pathGen(link as any) ?? ''}
              fill="none"
              stroke={color}
              strokeWidth={Math.max(1, link.width ?? 1)}
              strokeOpacity={isHov ? 0.65 : 0.2}
              style={{ cursor: 'pointer', transition: 'stroke-opacity 0.15s' }}
              onMouseEnter={() => setHoveredLink(link)}
              onMouseLeave={() => setHoveredLink(null)}
            />
          )
        })}

        {/* Nodes */}
        {(nodes as SNode[]).map((node, i) => {
          const x0 = node.x0 ?? 0
          const x1 = node.x1 ?? 0
          const y0 = node.y0 ?? 0
          const y1 = node.y1 ?? 0
          const h = Math.max(2, y1 - y0)
          const color = LEVEL_COLORS[node.lineLevel] ?? '#9ca3af'
          const midY = (y0 + y1) / 2
          const isLast = node.lineLevel === 3

          return (
            <g key={i}>
              <rect x={x0} y={y0} width={x1 - x0} height={h} fill={color} rx={2} />
              {h >= 10 && (
                <text
                  x={isLast ? x1 + 5 : x0 - 5}
                  y={midY}
                  dy="0.35em"
                  fontSize={10}
                  fill="#374151"
                  textAnchor={isLast ? 'start' : 'end'}
                  style={{ pointerEvents: 'none' }}
                >
                  {shorten(node.label)}
                </text>
              )}
            </g>
          )
        })}

        {/* Hovered link tooltip */}
        {hoveredLink && (
          <text
            x={WIDTH / 2 - PAD.right / 2}
            y={HEIGHT - 2}
            textAnchor="middle"
            fontSize={11}
            fill="#374151"
            style={{ pointerEvents: 'none' }}
          >
            {shorten(hoveredLink.fromLabel, 20)} → {shorten(hoveredLink.toLabel, 20)}
            {': '}
            {hoveredLink.n} patients ({hoveredLink.pct.toFixed(1)}%)
          </text>
        )}
      </svg>

      {/* Column headers */}
      <div className="flex justify-between mt-1 pr-28">
        {(['1st Line', '2nd Line', '3rd Line+'] as const).map((label, i) => (
          <span key={i} className="text-xs font-semibold text-gray-500">{label}</span>
        ))}
      </div>

      <p className="text-xs text-gray-400 mt-1">
        Flow width = number of patients switching between regimens. Hover a flow for details.
      </p>
    </div>
  )
}
