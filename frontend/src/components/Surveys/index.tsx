import { useEffect, useState } from 'react'
import {
  fetchSurveys,
  fetchSurveyQuestions,
  fetchSurveyCrosstab,
  fetchSurveyResponses,
  fetchSurveyResponsesExport,
} from '../../api/client'
import type { SurveySummary, SurveyQuestion, SurveyCrosstab, SurveyResponsesData } from '../../api/client'
import CrosstabHeatmap from './CrosstabHeatmap'
import NumericSummaryPlot from './NumericSummaryPlot'
import SurveyResponsesGrid from './SurveyResponsesGrid'

export default function Surveys() {
  const [surveys, setSurveys] = useState<SurveySummary[]>([])
  const [surveyId, setSurveyId] = useState('')
  const [questions, setQuestions] = useState<SurveyQuestion[]>([])
  const [x, setX] = useState('')
  const [y, setY] = useState('')
  const [includePartial, setIncludePartial] = useState(false)
  const [table, setTable] = useState<SurveyCrosstab | null>(null)
  const [responses, setResponses] = useState<SurveyResponsesData | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    fetchSurveys().then(data => {
      if (active) setSurveys(data)
    }).catch(() => { if (active) setError('Could not load surveys.') })
    return () => { active = false }
  }, [])

  // Auto-select when only one survey available
  useEffect(() => {
    if (surveys.length === 1 && !surveyId) {
      selectSurvey(surveys[0].id)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [surveys])

  useEffect(() => {
    if (!surveyId) return
    let active = true
    fetchSurveyQuestions(surveyId).then(data => {
      if (active) setQuestions(data)
    }).catch(() => { if (active) setError('Could not load questions.') })
    return () => { active = false }
  }, [surveyId])

  useEffect(() => {
    if (!surveyId) return
    let active = true
    fetchSurveyResponses(surveyId, includePartial)
      .then(d => { if (active) setResponses(d) })
      .catch(() => {})
    return () => { active = false }
  }, [surveyId, includePartial])

  useEffect(() => {
    if (!surveyId || !x || !y || x === y) return
    let active = true
    fetchSurveyCrosstab(surveyId, x, y, includePartial).then(data => {
      if (active) setTable(data)
    }).catch(() => { if (active) setError('Could not load crosstabulation.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [surveyId, x, y, includePartial])

  function selectSurvey(id: string) {
    setSurveyId(id)
    setQuestions([])
    setX('')
    setY('')
    setTable(null)
    setResponses(null)
    setError('')
  }

  function selectX(key: string) {
    setX(key)
    setTable(null)
    setError('')
    setLoading(Boolean(key && y && key !== y))
  }

  function selectY(key: string) {
    setY(key)
    setTable(null)
    setError('')
    setLoading(Boolean(key && x && key !== x))
  }

  async function downloadResponsesCSV() {
    if (!surveyId || !responses) return
    try {
      const exportData = await fetchSurveyResponsesExport(surveyId, includePartial)
      const { questions: qs, rows } = exportData
      const header = qs.map(q => `"${q.text.replace(/"/g, '""')}"`).join(',')
      const dataRows = rows.map(row =>
        qs.map(q => `"${(row.answers[q.key] ?? '').replace(/"/g, '""')}"`).join(',')
      )
      const csv = [header, ...dataRows].join('\n')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'survey_responses.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setError('Could not download responses CSV.')
    }
  }

  function downloadCrosstabCSV() {
    if (!table || !x || !y) return
    const xText = questions.find(q => q.key === x)?.text ?? x
    const yText = questions.find(q => q.key === y)?.text ?? y
    const header = [`"${yText.replace(/"/g, '""')}"`, ...table.x_values.map(v => `"${v.replace(/"/g, '""')}"`)]
    const cellMap = new Map<string, Map<string, number>>()
    for (const cell of table.cells) {
      if (!cellMap.has(cell.y)) cellMap.set(cell.y, new Map())
      cellMap.get(cell.y)!.set(cell.x, cell.count)
    }
    const dataRows = table.y_values.map(yVal => {
      const row = [`"${yVal.replace(/"/g, '""')}"`]
      for (const xVal of table.x_values) {
        row.push(String(cellMap.get(yVal)?.get(xVal) ?? 0))
      }
      return row
    })
    const csv = [[`"X: ${xText.replace(/"/g, '""')}"`, '', `"Y: ${yText.replace(/"/g, '""')}"`].join(',')]
    csv.push(header.join(','))
    for (const row of dataRows) csv.push(row.join(','))
    const blob = new Blob([csv.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'crosstab.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const chosenSurvey = surveys.find(s => s.id === surveyId)
  const xQuestion = questions.find(q => q.key === x)?.text ?? ''
  const yQuestion = questions.find(q => q.key === y)?.text ?? ''

  return <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-8">
    <div>
      <h2 className="text-xl font-semibold text-gray-900">Survey Analytics</h2>
      <p className="mt-1 text-sm text-gray-600">Aggregate analysis of submitted survey completions across all organisations. Cohort filters do not apply. Multi-select answers count in each selected category.</p>
    </div>

    {/* Survey picker — hidden when there is only one survey */}
    {surveys.length > 1 && (
      <div className="grid gap-4 md:grid-cols-3">
        <label className="text-sm font-medium text-gray-700">Survey
          <select aria-label="Survey" className="mt-2 block w-full rounded-lg border border-gray-300 p-2" value={surveyId} onChange={e => selectSurvey(e.target.value)}>
            <option value="">Choose a survey</option>
            {surveys.map(s => <option key={s.id} value={s.id}>{s.title} ({s.completions})</option>)}
          </select>
        </label>
      </div>
    )}
    {surveys.length === 1 && surveyId && (
      <p className="text-sm text-gray-700 font-medium">{surveys[0].title} <span className="text-gray-500 font-normal">({surveys[0].completions} completions)</span></p>
    )}

    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

    {/* Include partial checkbox */}
    {surveyId && (
      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          className="rounded border-gray-300"
          checked={includePartial}
          onChange={e => { setIncludePartial(e.target.checked); setTable(null); setResponses(null) }}
        />
        Include partial responders (answered questions but did not complete the full survey)
      </label>
    )}

    {/* Survey Responses section */}
    {surveyId && (
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-semibold text-gray-800">Survey Responses</h3>
          {responses && responses.questions.length > 0 && (
            <button
              onClick={downloadResponsesCSV}
              className="flex items-center gap-1 text-sm text-teal-700 hover:text-teal-900 underline underline-offset-2"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download CSV
            </button>
          )}
        </div>
        {responses
          ? <SurveyResponsesGrid data={responses} />
          : <p className="text-sm text-gray-500">Loading responses…</p>
        }
      </div>
    )}

    {/* Crosstab Analysis section */}
    {surveyId && (
      <div>
        <h3 className="text-base font-semibold text-gray-800 mb-3">Crosstab Analysis</h3>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="text-sm font-medium text-gray-700">X question
            <select aria-label="X question" className="mt-2 block w-full rounded-lg border border-gray-300 p-2" value={x} onChange={e => selectX(e.target.value)} disabled={!surveyId}>
              <option value="">Choose a question</option>
              {questions.filter(q => q.key !== y).map(q => <option key={q.key} value={q.key}>{q.text}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-gray-700">Y question
            <select aria-label="Y question" className="mt-2 block w-full rounded-lg border border-gray-300 p-2" value={y} onChange={e => selectY(e.target.value)} disabled={!surveyId}>
              <option value="">Choose a question</option>
              {questions.filter(q => q.key !== x).map(q => <option key={q.key} value={q.key}>{q.text}</option>)}
            </select>
          </label>
        </div>
        {loading && <p className="mt-5 text-sm text-gray-500">Loading crosstabulation…</p>}
        {chosenSurvey && table && !loading && (
          <div className="mt-6">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm text-gray-600">
                {table.paired_completions} of {chosenSurvey.completions} completions answered both questions{includePartial ? ', plus partial responders' : ''}.
                {table.x_n != null && !table.numeric_summaries?.length ? ` (X: n=${table.x_n}, Y: n=${table.y_n})` : ''}
              </p>
              {!table.numeric_summaries?.length && table.x_values.length > 0 && (
                <button
                  onClick={downloadCrosstabCSV}
                  className="flex items-center gap-1 text-sm text-teal-700 hover:text-teal-900 underline underline-offset-2"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download CSV
                </button>
              )}
            </div>
            {table.paired_completions === 0 ? <p className="text-sm text-gray-500">No paired answers for these questions.</p> :
              table.numeric_summaries?.length ?
                <NumericSummaryPlot summaries={table.numeric_summaries} xQuestion={xQuestion} yQuestion={yQuestion} /> :
                <CrosstabHeatmap data={table} xQuestion={xQuestion} yQuestion={yQuestion} />}
            <p className="mt-3 text-xs text-gray-500">A response with multiple selections can contribute to several {table.numeric_summaries?.length ? 'groups' : 'cells'}. Named treatments are matched to PRism's FL therapy options; descriptions without a clear match appear as Other / unmapped treatment.</p>
          </div>
        )}
      </div>
    )}
  </section>
}
