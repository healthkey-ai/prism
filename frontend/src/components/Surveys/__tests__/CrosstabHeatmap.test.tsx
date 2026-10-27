import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import CrosstabHeatmap from '../CrosstabHeatmap'

it('renders both answer axes and encodes zero and higher counts with different colors', () => {
  render(<CrosstabHeatmap
    xQuestion="Last treatment"
    yQuestion="Outcome"
    data={{
      paired_completions: 3, x_n: 3, y_n: 3,
      x_values: ['BR', 'R-CHOP'],
      y_values: ['Complete Response', 'Partial Response'],
      cells: [
        { x: 'BR', y: 'Complete Response', count: 3, pct: 100 },
        { x: 'R-CHOP', y: 'Complete Response', count: 0, pct: 0 },
        { x: 'BR', y: 'Partial Response', count: 1, pct: 33.3 },
        { x: 'R-CHOP', y: 'Partial Response', count: 0, pct: 0 },
      ],
    }}
  />)
  expect(screen.getByText('X: Last treatment')).toBeInTheDocument()
  expect(screen.getByText('Y: Outcome')).toBeInTheDocument()
  const high = screen.getByRole('img', { name: 'Complete Response with BR: 3 respondents (100%)' })
  const zero = screen.getByRole('img', { name: 'Complete Response with R-CHOP: 0 respondents (0%)' })
  expect(high).toHaveTextContent('3')
  expect(high).toHaveStyle({ backgroundColor: '#115e59' })
  expect(zero).toHaveStyle({ backgroundColor: '#f1f5f9' })
})

it('shows per-option counts and percentages next to axis labels', () => {
  render(<CrosstabHeatmap
    xQuestion="Last treatment"
    yQuestion="Outcome"
    data={{
      paired_completions: 3, x_n: 4, y_n: 3,
      x_values: ['BR', 'R-CHOP'],
      y_values: ['Complete Response', 'Partial Response'],
      cells: [
        { x: 'BR', y: 'Complete Response', count: 3, pct: 100 },
        { x: 'R-CHOP', y: 'Complete Response', count: 0, pct: 0 },
        { x: 'BR', y: 'Partial Response', count: 1, pct: 33.3 },
        { x: 'R-CHOP', y: 'Partial Response', count: 0, pct: 0 },
      ],
      x_option_counts: { BR: 3, 'R-CHOP': 1 },
      y_option_counts: { 'Complete Response': 2, 'Partial Response': 1 },
    }}
  />)
  // Column label: BR with 3/4 = 75%
  expect(screen.getByText('3 (75%)')).toBeInTheDocument()
  // Column label: R-CHOP with 1/4 = 25%
  expect(screen.getByText('1 (25%)')).toBeInTheDocument()
  // Row label: Complete Response with 2/3 = 66.7%
  expect(screen.getByText('2 (66.7%)')).toBeInTheDocument()
  // Row label: Partial Response with 1/3 = 33.3%
  expect(screen.getByText('1 (33.3%)')).toBeInTheDocument()
})
