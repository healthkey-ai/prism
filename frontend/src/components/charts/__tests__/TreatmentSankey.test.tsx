import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import TreatmentSankey from '../TreatmentSankey'

// Mirrors LINK_OPACITY in TreatmentSankey.tsx (not exported: react-refresh lint rule).
const LINK_OPACITY = { rest: 0.55, active: 0.9, dimmed: 0.3 }

const data = {
  from_1l: [
    {
      from_regimen: 'R-CHOP',
      n_switched: 30,
      switches: [
        { to_regimen: 'BR', n: 20, pct: 66.7 },
        { to_regimen: 'R2', n: 10, pct: 33.3 },
      ],
    },
  ],
  from_2l: [
    {
      from_regimen: 'BR',
      n_switched: 5,
      switches: [{ to_regimen: 'CAR-T', n: 5, pct: 100 }],
    },
  ],
}

function linkOpacities() {
  return screen
    .getAllByTestId('sankey-link')
    .map((el) => Number(el.getAttribute('stroke-opacity')))
}

describe('TreatmentSankey', () => {
  it('renders every flow clearly visible without hovering', () => {
    render(<TreatmentSankey data={data} />)
    const opacities = linkOpacities()
    expect(opacities).toHaveLength(3)
    opacities.forEach((o) => expect(o).toBe(LINK_OPACITY.rest))
    // Guard against regressing to a near-invisible resting state.
    expect(LINK_OPACITY.rest).toBeGreaterThanOrEqual(0.5)
  })

  it('emphasises the hovered flow and keeps the others legible', () => {
    render(<TreatmentSankey data={data} />)
    const links = screen.getAllByTestId('sankey-link')
    fireEvent.mouseEnter(links[0])

    const opacities = linkOpacities()
    expect(opacities[0]).toBe(LINK_OPACITY.active)
    expect(opacities[1]).toBe(LINK_OPACITY.dimmed)
    expect(opacities[2]).toBe(LINK_OPACITY.dimmed)
    expect(LINK_OPACITY.dimmed).toBeGreaterThanOrEqual(0.25)
    expect(screen.getByText(/R-CHOP → BR: 20 patients \(66\.7%\)/)).toBeInTheDocument()

    fireEvent.mouseLeave(links[0])
    linkOpacities().forEach((o) => expect(o).toBe(LINK_OPACITY.rest))
  })

  it('shows an empty state when there are no switches', () => {
    render(<TreatmentSankey data={{ from_1l: [], from_2l: [] }} />)
    expect(screen.getByText('No switching data available')).toBeInTheDocument()
  })
})
