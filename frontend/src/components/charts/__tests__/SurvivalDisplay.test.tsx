import { cloneElement, type ReactElement } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import SurvivalCurves from '../SurvivalCurves'
import SubgroupSurvival from '../SubgroupSurvival'
import ForestPlot from '../ForestPlot'

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactElement<{ width: number; height: number }> }) =>
      cloneElement(children, { width: 800, height: 340 }),
  }
})

const censored = {
  n: 10, events: 0, median: null,
  curve: [
    { time: 0, survival: 1, at_risk: 10 },
    { time: 24, survival: 1, at_risk: 1 },
  ],
}
const empty = { n: 0, events: 0, median: null, curve: [] }
const emptyStrat = { os: [], pfs: [] }
const subgroups = {
  by_stage: { os: [{ ...censored, label: 'R-ISS I' }], pfs: [] },
  by_cytogenetics: emptyStrat,
  by_sct: emptyStrat,
  by_mrd: emptyStrat,
}

describe('survival displays without recorded deaths', () => {
  it('draws landmark OS and labels time from the landmark', () => {
    const { container } = render(
      <SurvivalCurves data={{ os: censored, pfs: empty, efs: empty }} landmarkMonths={6} />
    )
    expect(container.querySelector('.recharts-line-curve')).toHaveAttribute('d')
    expect(screen.queryByText('No data available')).not.toBeInTheDocument()
    expect(screen.getByText(/No deaths were recorded/)).toBeInTheDocument()
    expect(screen.getByText('Months after 6-month landmark')).toBeInTheDocument()
  })

  it('draws subgroup OS and reports why the lines overlap', () => {
    const { container } = render(<SubgroupSurvival data={subgroups} />)
    expect(container.querySelector('.recharts-line-curve')).toHaveAttribute('d')
    expect(screen.getByText(/survival curves overlap at 100%/)).toBeInTheDocument()
    expect(screen.getAllByText('100.0%')).toHaveLength(3)
  })

  it('keeps the controls available after selecting an empty subgroup', async () => {
    const user = userEvent.setup()
    render(<SubgroupSurvival data={subgroups} />)
    await user.click(screen.getByRole('button', { name: 'MRD Status' }))
    expect(screen.getByText('No data available for this stratification')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'ISS Stage' }))
    expect(screen.getByText(/survival curves overlap at 100%/)).toBeInTheDocument()
  })

  it('explains why the forest plot cannot estimate hazard ratios', () => {
    const { container } = render(<ForestPlot data={[]} os={censored} />)
    expect(screen.getByText(/No recorded deaths.*Hazard ratios cannot be estimated/)).toBeInTheDocument()
    expect(container.querySelector('svg')).not.toBeInTheDocument()
  })

  it('uses the insufficient-data message when deaths exist but arms are too small', () => {
    render(<ForestPlot data={[]} os={{ ...censored, events: 2 }} />)
    expect(screen.getByText('Insufficient data for subgroup analysis')).toBeInTheDocument()
    expect(screen.queryByText(/No recorded deaths/)).not.toBeInTheDocument()
  })
})
