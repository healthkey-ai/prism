import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import CohortTabs from '../CohortTabs'
import type { CohortSeries, MetricsResponse } from '../../../types'

const m = (count: number) => ({ cohort: { count } }) as unknown as MetricsResponse
const series: CohortSeries[] = [
  { key: 'primary', label: 'Current cohort', color: '#111', metrics: m(10), loading: false },
  { key: 'saved:1', label: 'Stage I', color: '#222', metrics: m(4), loading: false },
  { key: 'saved:2', label: 'Pending', color: '#333', metrics: null, loading: true },
]

describe('CohortTabs', () => {
  it('shows the primary cohort first and switches on click', async () => {
    const user = userEvent.setup()
    render(<CohortTabs series={series}>{c => <div>chart for {c.label}</div>}</CohortTabs>)
    expect(screen.getByText('chart for Current cohort')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Stage I/ })).toHaveTextContent('n=4')
    await user.click(screen.getByRole('tab', { name: /Stage I/ }))
    expect(screen.getByText('chart for Stage I')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Stage I/ })).toHaveAttribute('aria-selected', 'true')
  })

  it('shows a loading state instead of the chart for a cohort still fetching', async () => {
    const user = userEvent.setup()
    render(<CohortTabs series={series}>{c => <div>chart for {c.label}</div>}</CohortTabs>)
    await user.click(screen.getByRole('tab', { name: /Pending/ }))
    expect(screen.getByText('Loading…')).toBeInTheDocument()
    expect(screen.queryByText('chart for Pending')).not.toBeInTheDocument()
  })

  it('keeps the selected cohort when an earlier cohort is removed', async () => {
    const user = userEvent.setup()
    const { rerender } = render(<CohortTabs series={series}>{c => <div>chart for {c.label}</div>}</CohortTabs>)
    await user.click(screen.getByRole('tab', { name: /Pending/ }))
    rerender(<CohortTabs series={[series[0], series[2]]}>{c => <div>chart for {c.label}</div>}</CohortTabs>)
    expect(screen.getByRole('tab', { name: /Pending/ })).toHaveAttribute('aria-selected', 'true')
  })
})
