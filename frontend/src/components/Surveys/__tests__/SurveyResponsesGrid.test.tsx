import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import SurveyResponsesGrid from '../SurveyResponsesGrid'
import type { SurveyResponsesData } from '../../../api/client'

const mockData: SurveyResponsesData = {
  total_responses: 10,
  include_partial: false,
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
  render(<SurveyResponsesGrid data={{ total_responses: 0, include_partial: false, questions: [] }} />)
  expect(screen.getByText(/No categorical questions with responses found/)).toBeInTheDocument()
})

it('encodes max-count option with darkest color', () => {
  render(<SurveyResponsesGrid data={mockData} />)
  // BR has count=5, maximum=5, so fraction=1 → COLORS[5] = '#115e59'
  const brCell = screen.getByRole('img', { name: /Which treatments have you had\? — BR: 5 \(62\.5%\)/ })
  expect(brCell).toHaveStyle({ backgroundColor: '#115e59' })
})

const numberedData: SurveyResponsesData = {
  total_responses: 4,
  include_partial: false,
  questions: [
    {
      key: 'q1_country',
      number: '1',
      text: 'Which country do you live in?',
      n: 3,
      options: [
        { label: 'GB', count: 2, pct: 66.7, title: 'United Kingdom' },
        { label: 'US', count: 1, pct: 33.3, title: 'United States' },
      ],
      zero_options: ['France', 'Germany', 'Spain'],
    },
    {
      key: 'q11_cart_informed',
      number: '11',
      text: 'How well informed do you feel about CAR-T therapy?',
      n: 4,
      options: [
        { label: '1 – Not informed at all', count: 3, pct: 75 },
        { label: '5 – Very well informed', count: 1, pct: 25 },
      ],
      zero_options: ['2', '3', '4'],
    },
  ],
}

it('prefixes the question number', () => {
  render(<SurveyResponsesGrid data={numberedData} />)
  expect(screen.getByText('Q1. Which country do you live in?')).toBeInTheDocument()
  expect(screen.getByText('Q11. How well informed do you feel about CAR-T therapy?')).toBeInTheDocument()
})

it('shows the country code with the full name as the tooltip', () => {
  render(<SurveyResponsesGrid data={numberedData} />)
  expect(screen.getByText('GB')).toBeInTheDocument()
  const cell = screen.getByRole('img', { name: /United Kingdom: 2 \(66\.7%\)/ })
  expect(cell).toHaveAttribute('title', 'United Kingdom: 2 respondents (66.7%)')
})

it('adds a trailing zero cell listing every option with no responses', () => {
  render(<SurveyResponsesGrid data={numberedData} />)
  const zero = screen.getByRole('img', { name: /3 options with no responses: France, Germany, Spain/ })
  expect(zero).toHaveAttribute('title', 'No responses (3): France, Germany, Spain')
  expect(zero).toHaveTextContent('3 others')
  expect(zero).toHaveTextContent('0')
  expect(screen.getByRole('img', { name: /no responses: 2, 3, 4/ })).toBeInTheDocument()
})

it('omits the zero cell when the option set is not known', () => {
  render(<SurveyResponsesGrid data={mockData} />)
  expect(screen.queryByRole('img', { name: /no responses/ })).not.toBeInTheDocument()
})
