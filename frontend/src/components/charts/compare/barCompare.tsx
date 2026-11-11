import { useState } from 'react'
import type { CohortSeries, MetricsResponse, TherapyCount, TherapyOutcomes } from '../../../types'
import { pctOf, type CategoryRow } from '../../../utils/cohortCompare'
import GroupedBarCompare from './GroupedBarCompare'

/** Rows per series, with an empty list for cohorts whose metrics are missing. */
function rowsFor(series: CohortSeries[], pick: (m: MetricsResponse) => CategoryRow[]): CategoryRow[][] {
  return series.map(s => (s.metrics ? pick(s.metrics) : []))
}

function shortName(name: string): string {
  return name.split(' (')[0]
}

function Toggle<K extends string>({ options, value, onChange }: {
  options: { key: K; label: string }[]; value: K; onChange: (k: K) => void
}) {
  return (
    <div className="flex gap-1 rounded-lg border border-gray-200 p-0.5 bg-gray-50 w-fit mb-4">
      {options.map(o => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          className={`px-4 py-1.5 text-xs rounded-md font-semibold transition-colors ${
            o.key === value ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function CohortChips({ series, value }: { series: CohortSeries[]; value: (m: MetricsResponse) => string | null }) {
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {series.map(s => {
        const v = s.metrics ? value(s.metrics) : null
        return (
          <span key={s.key} className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs text-gray-600">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: s.color }} />
            <span className="font-medium truncate max-w-[140px]">{s.label}</span>
            <span className="font-bold text-gray-900">{v ?? '—'}</span>
          </span>
        )
      })}
    </div>
  )
}

/* ---------- Treatment patterns ---------- */

export function TreatmentPatternsCompare({ series, rows }: { series: CohortSeries[]; rows: TherapyCount[][] }) {
  const data = rows.map(r => r.map(t => ({ name: shortName(t.therapy), value: t.pct })))
  return <GroupedBarCompare series={series} rows={data} unit="pct" />
}

/* ---------- Response rates (ORR per therapy) ---------- */

export function ResponseRatesCompare({ series, rows, title }: { series: CohortSeries[]; rows: TherapyOutcomes[][]; title: string }) {
  const data = rows.map(r => r.map(t => ({ name: shortName(t.therapy), value: t.orr_pct })))
  return (
    <div>
      <span className="text-sm font-medium text-gray-700 block mb-3">{title} — overall response rate</span>
      <GroupedBarCompare series={series} rows={data} unit="pct" />
      <p className="text-xs text-gray-400 mt-2">Overall response rate (≥PR) per therapy, as a share of each cohort's patients on that therapy.</p>
    </div>
  )
}

/* ---------- Therapy categories ---------- */

type LineKey = 'first_line' | 'second_line' | 'later_line'
const LINE_TABS: { key: LineKey; label: string }[] = [
  { key: 'first_line',  label: '1st Line' },
  { key: 'second_line', label: '2nd Line' },
  { key: 'later_line',  label: '3rd Line+' },
]

export function TherapyCategoriesCompare({ series }: { series: CohortSeries[] }) {
  const [line, setLine] = useState<LineKey>('first_line')
  const rows = rowsFor(series, m => (m.therapy_categories?.[line] ?? []).map(r => ({ name: r.category, value: r.pct })))
  return (
    <div>
      <Toggle options={LINE_TABS} value={line} onChange={setLine} />
      <GroupedBarCompare series={series} rows={rows} unit="pct" categoryWidth={150} emptyMessage="No data available for this line" />
    </div>
  )
}

/* ---------- Lines of therapy ---------- */

export function TreatmentLinesCompare({ series }: { series: CohortSeries[] }) {
  const funnel = rowsFor(series, m => (m.treatment_patterns?.line_funnel ?? []).map(r => ({ name: r.label, value: r.pct })))
  const dist = rowsFor(series, m => (m.treatment_patterns?.line_distribution ?? []).map(r => ({ name: r.label, value: r.pct })))
  return (
    <div>
      <CohortChips series={series} value={m => {
        const b = m.treatment_patterns?.burden
        return b ? `median ${b.median_lines ?? '—'} · ≥2: ${b.ge2_pct.toFixed(1)}% · ≥3: ${b.ge3_pct.toFixed(1)}%` : null
      }} />
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Patients Reaching Each Line</p>
          <GroupedBarCompare series={series} rows={funnel} unit="pct" categoryWidth={40} height={220} />
        </div>
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Lines of Therapy Distribution</p>
          <GroupedBarCompare series={series} rows={dist} unit="pct" categoryWidth={60} height={220} />
        </div>
      </div>
    </div>
  )
}

/* ---------- CR by landmark ---------- */

export function LandmarkResponseCompare({ series }: { series: CohortSeries[] }) {
  const rows = rowsFor(series, m =>
    (m.landmark_response?.landmarks ?? []).filter(l => l.evaluable > 0).map(l => ({ name: `CR${l.months}`, value: l.pct })))
  return (
    <div>
      <GroupedBarCompare series={series} rows={rows} unit="pct" layout="horizontal" height={240} />
      <p className="text-xs text-gray-400 mt-2">Proportion of evaluable first-line patients in complete response within each landmark (months).</p>
    </div>
  )
}

/* ---------- Time to first treatment ---------- */

export function TimeToTreatmentCompare({ series }: { series: CohortSeries[] }) {
  const rows = rowsFor(series, m => {
    const t = m.time_to_treatment
    if (!t) return []
    return t.histogram.map(h => ({ name: h.label, value: pctOf(h.count, t.n) }))
  })
  return (
    <div>
      <CohortChips series={series} value={m => {
        const t = m.time_to_treatment
        return t?.median_days != null ? `median ${t.median_days} d (n=${t.n})` : null
      }} />
      <GroupedBarCompare series={series} rows={rows} unit="pct" layout="horizontal" height={220} emptyMessage="No time-to-treatment data available" />
      <p className="text-xs text-gray-400 mt-1 text-center">Days from diagnosis to first treatment, as a share of each cohort</p>
    </div>
  )
}

/* ---------- Disease state ---------- */

export function DiseaseStateCompare({ series }: { series: CohortSeries[] }) {
  const rows = rowsFor(series, m => (m.disease_state?.states ?? []).map(s => ({ name: s.label, value: s.pct })))
  return <GroupedBarCompare series={series} rows={rows} unit="pct" layout="horizontal" height={240} />
}

/* ---------- Demographics ---------- */

export function DemographicsCompare({ series }: { series: CohortSeries[] }) {
  const age = rowsFor(series, m => (m.demographics?.age_distribution ?? []).map(r => ({ name: r.bucket, value: r.pct })))
  const gender = rowsFor(series, m => (m.demographics?.gender ?? []).map(r => ({ name: r.gender, value: r.pct })))
  const race = rowsFor(series, m => (m.demographics?.race ?? []).map(r => ({ name: r.race, value: r.pct })))
  const ethnicity = rowsFor(series, m => (m.demographics?.ethnicity ?? []).map(r => ({ name: r.ethnicity, value: r.pct })))
  const panels: { title: string; rows: CategoryRow[][]; layout: 'horizontal' | 'vertical'; width?: number }[] = [
    { title: 'Age Distribution', rows: age, layout: 'horizontal' },
    { title: 'Gender', rows: gender, layout: 'vertical', width: 80 },
    { title: 'Race', rows: race, layout: 'vertical', width: 180 },
    { title: 'Ethnicity', rows: ethnicity, layout: 'vertical', width: 120 },
  ]
  return (
    <div className="grid grid-cols-2 gap-6">
      {panels.map(p => (
        <div key={p.title}>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{p.title}</p>
          <GroupedBarCompare series={series} rows={p.rows} unit="pct" layout={p.layout} categoryWidth={p.width} emptyMessage="No data" />
        </div>
      ))}
    </div>
  )
}
