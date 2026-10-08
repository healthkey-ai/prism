import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import NumericSummaryPlot from '../NumericSummaryPlot'

it('plots a Y scale mean with vertical SD bars for each X answer', () => {
  const { container } = render(<NumericSummaryPlot
    xQuestion="Treatment"
    yQuestion="Well-being score"
    summaries={[{ axis: 'y', groups: [
      { label: 'BR', n: 3, mean: 4, sd: 1 },
      { label: 'R-CHOP', n: 1, mean: 2, sd: null },
    ] }]}
  />)
  expect(screen.getByRole('figure', { name: 'Numeric survey mean and standard deviation chart' })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'Mean Well-being score by Treatment, with standard deviation bars' })).toBeInTheDocument()
  expect(screen.getByText('X: Treatment')).toBeInTheDocument()
  expect(screen.getByText('Y: Well-being score')).toBeInTheDocument()
  expect(screen.getByText('4 ± 1 (n=3)')).toBeInTheDocument()
  expect(screen.getByText('2 (n=1)')).toBeInTheDocument()
  expect(container.querySelectorAll('circle')).toHaveLength(2)
})

it('plots an X scale mean with horizontal SD bars', () => {
  render(<NumericSummaryPlot
    xQuestion="Well-being score"
    yQuestion="Treatment"
    summaries={[{ axis: 'x', groups: [{ label: 'BR', n: 3, mean: 4, sd: 1 }] }]}
  />)
  expect(screen.getByRole('img', { name: 'Mean Well-being score by Treatment, with standard deviation bars' })).toBeInTheDocument()
  expect(screen.getByText('X: Well-being score')).toBeInTheDocument()
  expect(screen.getByText('Y: Treatment')).toBeInTheDocument()
})

it('shows both numeric means with X and Y deviation bars', () => {
  const { container } = render(<NumericSummaryPlot
    xQuestion="Score A"
    yQuestion="Score B"
    summaries={[
      { axis: 'x', groups: [{ label: 'All paired responses', n: 4, mean: 2, sd: 0.5 }] },
      { axis: 'y', groups: [{ label: 'All paired responses', n: 4, mean: 3, sd: 1 }] },
    ]}
  />)
  expect(screen.getByRole('img', { name: 'Mean Score A and Score B, with standard deviation bars for 4 paired completions' })).toBeInTheDocument()
  expect(container.querySelectorAll('circle')).toHaveLength(1)
})
