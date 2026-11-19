import { cloneElement, type ReactElement } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import KMCompare from '../KMCompare'
import { SURVIVAL_OPTIONS } from '../kmOptions'
import GroupedBarCompare from '../GroupedBarCompare'
import { TreatmentPatternsCompare } from '../barCompare'
import type { CohortSeries, MetricsResponse, SurvivalLine } from '../../../../types'

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactElement<{ width: number; height: number }> }) =>
      cloneElement(children, { width: 800, height: 340 }),
  }
})

const line = (n: number, median: number | null): SurvivalLine => ({
  n, median,
  curve: [{ time: 0, survival: 1, at_risk: n }, { time: 12, survival: 0.6, at_risk: 1 }],
})
const empty: SurvivalLine = { n: 0, median: null, curve: [] }

const metrics = (os: SurvivalLine, pfs: SurvivalLine): MetricsResponse =>
  ({ cohort: { count: os.n }, survival: { os, pfs, efs: empty } }) as unknown as MetricsResponse

const series: CohortSeries[] = [
  { key: 'primary', label: 'Current cohort', color: '#0d9488', metrics: metrics(line(10, 20), line(10, 8)), loading: false },
  { key: 'saved:1', label: 'High risk', color: '#2563eb', metrics: metrics(line(5, 9), empty), loading: false },
  { key: 'saved:2', label: 'Failed', color: '#d97706', metrics: null, loading: false },
]

describe('KMCompare', () => {
  it('draws one line per cohort that has data, in the cohort colors', () => {
    const { container } = render(<KMCompare series={series} options={SURVIVAL_OPTIONS} />)
    const paths = container.querySelectorAll('.recharts-line-curve')
    // 2 cohorts × (line + lower CI + upper CI) — CI lines render even without CI data.
    expect(paths.length).toBeGreaterThanOrEqual(2)
    expect(container.querySelector('.recharts-line-curve[stroke="#0d9488"]')).not.toBeNull()
    expect(container.querySelector('.recharts-line-curve[stroke="#2563eb"]')).not.toBeNull()
    expect(container.querySelector('.recharts-line-curve[stroke="#d97706"]')).toBeNull()
    expect(screen.getByText('Current cohort')).toBeInTheDocument()
    expect(screen.getByText(/median 20.0 mo/)).toBeInTheDocument()
    expect(screen.queryByText('Failed')).not.toBeInTheDocument()
  })

  it('switches metric with the toggle and drops cohorts lacking that metric', async () => {
    const user = userEvent.setup()
    const { container } = render(<KMCompare series={series} options={SURVIVAL_OPTIONS} />)
    await user.click(screen.getByRole('button', { name: 'PFS' }))
    expect(container.querySelector('.recharts-line-curve[stroke="#0d9488"]')).not.toBeNull()
    expect(container.querySelector('.recharts-line-curve[stroke="#2563eb"]')).toBeNull()
    expect(screen.getByText(/median 8.0 mo/)).toBeInTheDocument()
  })
})

describe('GroupedBarCompare', () => {
  it('renders a bar series per cohort and an empty message with no rows', () => {
    const { container, rerender } = render(
      <GroupedBarCompare series={series.slice(0, 2)} rows={[[{ name: 'VRd', value: 40 }], [{ name: 'VRd', value: 55 }]]} />
    )
    expect(container.querySelectorAll('.recharts-bar').length).toBe(2)
    rerender(<GroupedBarCompare series={series.slice(0, 2)} rows={[[], []]} emptyMessage="Nothing here" />)
    expect(screen.getByText('Nothing here')).toBeInTheDocument()
  })
})

describe('TreatmentPatternsCompare', () => {
  it('plots regimen share for every cohort on a shared axis', () => {
    const { container } = render(
      <TreatmentPatternsCompare
        series={series.slice(0, 2)}
        rows={[
          [{ therapy: 'VRd (bortezomib)', count: 4, pct: 40 }],
          [{ therapy: 'DRd (daratumumab)', count: 3, pct: 60 }, { therapy: 'VRd (bortezomib)', count: 2, pct: 40 }],
        ]}
      />
    )
    // jsdom does not lay out axis ticks; assert on the per-cohort bar series and legend.
    expect(container.querySelectorAll('.recharts-bar').length).toBe(2)
    expect(screen.getByText('Current cohort')).toBeInTheDocument()
    expect(screen.getByText('High risk')).toBeInTheDocument()
  })
})
