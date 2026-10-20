import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import CrosstabHeatmap from '../CrosstabHeatmap'

it('renders both answer axes and encodes zero and higher counts with different colors', () => {
  render(<CrosstabHeatmap
    xQuestion="Last treatment"
    yQuestion="Outcome"
    data={{
      paired_completions: 3,
      x_values: ['BR', 'R-CHOP'],
      y_values: ['Complete Response', 'Partial Response'],
      cells: [
        { x: 'BR', y: 'Complete Response', count: 3 },
        { x: 'R-CHOP', y: 'Complete Response', count: 0 },
        { x: 'BR', y: 'Partial Response', count: 1 },
        { x: 'R-CHOP', y: 'Partial Response', count: 0 },
      ],
    }}
  />)
  expect(screen.getByText('X: Last treatment')).toBeInTheDocument()
  expect(screen.getByText('Y: Outcome')).toBeInTheDocument()
  const high = screen.getByRole('img', { name: 'Complete Response with BR: 3 completions' })
  const zero = screen.getByRole('img', { name: 'Complete Response with R-CHOP: 0 completions' })
  expect(high).toHaveTextContent('3')
  expect(high).toHaveStyle({ backgroundColor: '#115e59' })
  expect(zero).toHaveStyle({ backgroundColor: '#f1f5f9' })
})
