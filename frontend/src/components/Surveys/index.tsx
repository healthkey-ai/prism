import { useEffect, useState } from 'react'
import { fetchSurveys, fetchSurveyQuestions, fetchSurveyCrosstab } from '../../api/client'
import type { SurveySummary, SurveyQuestion, SurveyCrosstab } from '../../api/client'
import CrosstabHeatmap from './CrosstabHeatmap'

export default function Surveys() {
  const [surveys, setSurveys] = useState<SurveySummary[]>([])
  const [surveyId, setSurveyId] = useState('')
  const [questions, setQuestions] = useState<SurveyQuestion[]>([])
  const [x, setX] = useState('')
  const [y, setY] = useState('')
  const [table, setTable] = useState<SurveyCrosstab | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    fetchSurveys().then(data => {
      if (active) setSurveys(data)
    }).catch(() => { if (active) setError('Could not load surveys.') })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!surveyId) return
    let active = true
    fetchSurveyQuestions(surveyId).then(data => {
      if (active) setQuestions(data)
    }).catch(() => { if (active) setError('Could not load questions.') })
    return () => { active = false }
  }, [surveyId])

  useEffect(() => {
    if (!surveyId || !x || !y || x === y) return
    let active = true
    fetchSurveyCrosstab(surveyId, x, y).then(data => {
      if (active) setTable(data)
    }).catch(() => { if (active) setError('Could not load crosstabulation.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [surveyId, x, y])

  function selectSurvey(id: string) {
    setSurveyId(id)
    setQuestions([])
    setX('')
    setY('')
    setTable(null)
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

  const chosenSurvey = surveys.find(s => s.id === surveyId)
  const xQuestion = questions.find(q => q.key === x)?.text ?? ''
  const yQuestion = questions.find(q => q.key === y)?.text ?? ''

  return <section className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
    <h2 className="text-xl font-semibold text-gray-900">Crosstabulation Analysis</h2>
    <p className="mt-1 text-sm text-gray-600">Compare answers from submitted survey completions across all organisations. Cohort filters do not apply. Multi-select answers count in each selected category.</p>
    <div className="mt-6 grid gap-4 md:grid-cols-3">
      <label className="text-sm font-medium text-gray-700">Survey
        <select aria-label="Survey" className="mt-2 block w-full rounded-lg border border-gray-300 p-2" value={surveyId} onChange={e => selectSurvey(e.target.value)}>
          <option value="">Choose a survey</option>
          {surveys.map(s => <option key={s.id} value={s.id}>{s.title} ({s.completions})</option>)}
        </select>
      </label>
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
    {error && <p role="alert" className="mt-5 text-sm text-red-700">{error}</p>}
    {loading && <p className="mt-5 text-sm text-gray-500">Loading crosstabulation…</p>}
    {chosenSurvey && table && !loading && <div className="mt-6">
      <p className="mb-3 text-sm text-gray-600">{table.paired_completions} of {chosenSurvey.completions} completions answered both questions.</p>
      {table.paired_completions === 0 ? <p className="text-sm text-gray-500">No paired answers for these questions.</p> :
        <CrosstabHeatmap data={table} xQuestion={xQuestion} yQuestion={yQuestion} />}
      <p className="mt-3 text-xs text-gray-500">A response with multiple selections can contribute to several cells. Named treatments are matched to PRism’s FL therapy options; descriptions without a clear match appear as Other / unmapped treatment.</p>
    </div>}
  </section>
}
