import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Surveys from '..'
import * as client from '../../../api/client'

function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsText(blob)
  })
}

vi.mock('../../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/client')>()
  return {
    ...actual,
    fetchSurveys: vi.fn(),
    fetchSurveyQuestions: vi.fn(),
    fetchSurveyCrosstab: vi.fn(),
    fetchSurveyResponses: vi.fn(),
    fetchSurveyResponsesExport: vi.fn(),
  }
})

beforeEach(() => {
  vi.mocked(client.fetchSurveys).mockResolvedValue([
    { id: 'survey-1', title: 'FL survey', completions: 3 },
    { id: 'survey-2', title: 'Another survey', completions: 1 },
  ])
  vi.mocked(client.fetchSurveyResponses).mockResolvedValue({ total_responses: 3, include_partial: false, questions: [] })
  vi.mocked(client.fetchSurveyQuestions).mockResolvedValue([
    { key: 'a', text: 'Treatment?', type: 'multi' },
    { key: 'b', text: 'Country?', type: 'single' },
  ])
  vi.mocked(client.fetchSurveyCrosstab).mockResolvedValue({
    paired_completions: 2, x_n: 2, y_n: 2, x_values: ['BR'], y_values: ['UK'],
    cells: [{ x: 'BR', y: 'UK', count: 2, pct: 100 }],
  })
})

it('loads selections and shows the paired count and crosstab', async () => {
  const user = userEvent.setup()
  render(<Surveys />)
  await user.selectOptions(await screen.findByLabelText('Survey'), 'survey-1')
  await user.selectOptions(await screen.findByLabelText('X question'), 'a')
  await user.selectOptions(screen.getByLabelText('Y question'), 'b')
  expect(await screen.findByText(/2 of 3 completions answered both questions/)).toBeInTheDocument()
  expect(screen.getByRole('figure', { name: 'Crosstabulation heatmap' })).toBeInTheDocument()
  expect(screen.getByText('X: Treatment?')).toBeInTheDocument()
  expect(screen.getByText('Y: Country?')).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'UK with BR: 2 respondents (100%)' })).toBeInTheDocument()
  await waitFor(() => expect(client.fetchSurveyCrosstab).toHaveBeenCalledWith('survey-1', 'a', 'b', false, undefined))
})

it('downloads responses CSV with Respondent ID column and no Email column', async () => {
  const user = userEvent.setup()
  vi.mocked(client.fetchSurveyResponses).mockResolvedValue({
    total_responses: 1, include_partial: false,
    questions: [{ key: 'q1', text: 'Treatment?', type: 'single', n: 1, options: [{ label: 'BR', count: 1, pct: 100 }] }],
  })
  vi.mocked(client.fetchSurveyResponsesExport).mockResolvedValue({
    questions: [{ key: 'q1', text: 'Treatment?' }],
    rows: [{ respondent_id: 'r1', answers: { q1: 'BR' } }],
    truncated: false,
  })
  const createObjectURL = vi.fn(() => 'blob:test')
  URL.createObjectURL = createObjectURL
  URL.revokeObjectURL = vi.fn()

  render(<Surveys />)
  await user.selectOptions(await screen.findByLabelText('Survey'), 'survey-1')
  const btn = await screen.findByRole('button', { name: 'Download survey responses CSV' })
  await user.click(btn)

  await waitFor(() => expect(client.fetchSurveyResponsesExport).toHaveBeenCalledWith('survey-1', false, undefined))
  expect(createObjectURL).toHaveBeenCalledOnce()
  const blob: Blob = createObjectURL.mock.calls[0][0]
  const text = await readBlob(blob)
  expect(text).toContain('"Respondent ID"')
  expect(text).not.toContain('"Email"')
  expect(text).toContain('BR')
})

it('forwards cohort filters to fetchSurveyResponses', async () => {
  const user = userEvent.setup()
  const filters = { disease: 'Follicular Lymphoma', stage: [] as string[] }
  render(<Surveys filters={filters} />)
  await user.selectOptions(await screen.findByLabelText('Survey'), 'survey-1')
  await waitFor(() =>
    expect(client.fetchSurveyResponses).toHaveBeenCalledWith('survey-1', false, filters)
  )
})

it('shows cohort-active note when filters are set', async () => {
  render(<Surveys filters={{ disease: 'Follicular Lymphoma', stage: [] as string[] }} />)
  expect(await screen.findByText(/scoped to the active cohort/)).toBeInTheDocument()
})

it('shows all-responses note when no filters are set', async () => {
  render(<Surveys />)
  expect(await screen.findByText(/all responses are shown/)).toBeInTheDocument()
})

it('uses a mean and SD chart when a selected answer is numeric', async () => {
  vi.mocked(client.fetchSurveyQuestions).mockResolvedValue([
    { key: 'a', text: 'Treatment?', type: 'single' },
    { key: 'b', text: 'Well-being score?', type: 'scale' },
  ])
  vi.mocked(client.fetchSurveyCrosstab).mockResolvedValue({
    paired_completions: 2, x_n: 2, y_n: 2, x_values: [], y_values: [], cells: [],
    numeric_summaries: [{ axis: 'y', groups: [{ label: 'BR', n: 2, mean: 3, sd: 1 }] }],
  })
  const user = userEvent.setup()
  render(<Surveys />)
  await user.selectOptions(await screen.findByLabelText('Survey'), 'survey-1')
  await user.selectOptions(await screen.findByLabelText('X question'), 'a')
  await user.selectOptions(screen.getByLabelText('Y question'), 'b')
  expect(await screen.findByRole('figure', { name: 'Numeric survey mean and standard deviation chart' })).toBeInTheDocument()
  expect(screen.queryByRole('figure', { name: 'Crosstabulation heatmap' })).not.toBeInTheDocument()
})
