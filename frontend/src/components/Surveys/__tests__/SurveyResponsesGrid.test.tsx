import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import SurveyResponsesGrid from '../SurveyResponsesGrid'
import type { SurveyResponsesData } from '../../../api/client'

const mockData: SurveyResponsesData = {
  total_submitted: 10,
  questions: [
    {
      key: 'treatments',
      text: 'Which treatments have you had?',
      n: 8,
      options: [
        { label: 'BR', count: 5, pct: 62.5 },
        { label: 'R-CHOP', count: 3, pct: 37.5 },
      ],
    },
    {
      key: 'country',
      text: 'Country',
      n: 9,
      options: [
        { label: 'United Kingdom', count: 6, pct: 66.7 },
        { label: 'USA', count: 3, pct: 33.3 },
      ],
    },
  ],
}

it('renders question text', () => {
  render(<SurveyResponsesGrid data={mockData} />)
  expect(screen.getByText('Which treatments have you had?')).toBeInTheDocument()
  expect(screen.getByText('Country')).toBeInTheDocument()
})

it('renders option labels', () => {
  render(<SurveyResponsesGrid data={mockData} />)
  expect(screen.getByText('BR')).toBeInTheDocument()
  expect(screen.getByText('R-CHOP')).toBeInTheDocument()
  expect(screen.getByText('United Kingdom')).toBeInTheDocument()
  expect(screen.getByText('USA')).toBeInTheDocument()
})

it('renders count values', () => {
  render(<SurveyResponsesGrid data={mockData} />)
  // BR count (unique in the document — only 5 appears once)
  expect(screen.getByText('5')).toBeInTheDocument()
  // Both cells with count 3 are present (R-CHOP and USA both have count=3)
  expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(2)
})

it('renders row totals with n and percentage', () => {
  render(<SurveyResponsesGrid data={mockData} />)
  // treatments: n=8, pct=8/10=80%
  expect(screen.getByText('n=8 (80%)')).toBeInTheDocument()
  // country: n=9, pct=9/10=90%
  expect(screen.getByText('n=9 (90%)')).toBeInTheDocument()
})

it('renders empty state message when no questions', () => {
  render(<SurveyResponsesGrid data={{ total_submitted: 0, questions: [] }} />)
  expect(screen.getByText(/No categorical questions with responses found/)).toBeInTheDocument()
})

it('encodes max-count option with darkest color', () => {
  render(<SurveyResponsesGrid data={mockData} />)
  // BR has count=5, maximum=5, so fraction=1 → COLORS[5] = '#115e59'
  const brCell = screen.getByRole('img', { name: /Which treatments have you had\? — BR: 5 \(62\.5%\)/ })
  expect(brCell).toHaveStyle({ backgroundColor: '#115e59' })
})
