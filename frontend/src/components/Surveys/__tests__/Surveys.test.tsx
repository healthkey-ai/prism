import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import Surveys from '..'
import * as client from '../../../api/client'

vi.mock('../../../api/client', () => ({
  fetchSurveys: vi.fn(),
  fetchSurveyQuestions: vi.fn(),
  fetchSurveyCrosstab: vi.fn(),
}))

beforeEach(() => {
  vi.mocked(client.fetchSurveys).mockResolvedValue([{ id: 'survey-1', title: 'FL survey', completions: 3 }])
  vi.mocked(client.fetchSurveyQuestions).mockResolvedValue([
    { key: 'a', text: 'Treatment?', type: 'multi' },
    { key: 'b', text: 'Country?', type: 'single' },
  ])
  vi.mocked(client.fetchSurveyCrosstab).mockResolvedValue({
    paired_completions: 2, x_values: ['BR'], y_values: ['UK'],
    cells: [{ x: 'BR', y: 'UK', count: 2 }],
  })
})

it('loads selections and shows the paired count and crosstab', async () => {
  const user = userEvent.setup()
  render(<Surveys />)
  await user.selectOptions(await screen.findByLabelText('Survey'), 'survey-1')
  await user.selectOptions(await screen.findByLabelText('X question'), 'a')
  await user.selectOptions(screen.getByLabelText('Y question'), 'b')
  expect(await screen.findByText('2 of 3 completions answered both questions.')).toBeInTheDocument()
  expect(screen.getByRole('figure', { name: 'Crosstabulation heatmap' })).toBeInTheDocument()
  expect(screen.getByText('X: Treatment?')).toBeInTheDocument()
  expect(screen.getByText('Y: Country?')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'UK with BR: 2 completions' })).toBeInTheDocument()
  await waitFor(() => expect(client.fetchSurveyCrosstab).toHaveBeenCalledWith('survey-1', 'a', 'b'))
})
