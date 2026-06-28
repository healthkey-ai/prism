import type { MetricsResponse } from '../../types'

type Data = NonNullable<MetricsResponse['cohort_characterization']>

interface Props { data: Data }

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <tr className="border-b border-gray-100">
      <td className="py-1.5 pr-4 text-sm text-gray-600 pl-6">{label}</td>
      <td className="py-1.5 text-sm text-gray-900 font-medium text-right pr-4">
        {value ?? '—'}
      </td>
    </tr>
  )
}

function SectionHeader({ label }: { label: string }) {
  return (
    <tr className="bg-gray-50">
      <td colSpan={2} className="py-1.5 pl-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
        {label}
      </td>
    </tr>
  )
}

function fmt(n: number | null | undefined, pct: number | null | undefined): string | null {
  if (n == null) return null
  if (pct == null) return String(n)
  return `${n} (${pct}%)`
}

function fmtMedianIQR(
  med: number | null | undefined,
  q1: number | null | undefined,
  q3: number | null | undefined,
  unit = ''
): string | null {
  if (med == null) return null
  const u = unit ? ` ${unit}` : ''
  if (q1 != null && q3 != null) return `${med}${u} (IQR ${q1}–${q3})`
  return `${med}${u}`
}

export default function CohortCharacterization({ data }: Props) {
  const { n, demographics: d, receptor_status: rs, stages, ecog, treatment: tx, mrd, labs } = data

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b-2 border-gray-200">
            <th className="pb-2 pl-3 text-sm font-semibold text-gray-700">Characteristic</th>
            <th className="pb-2 pr-4 text-sm font-semibold text-gray-700 text-right">
              N = {n}
            </th>
          </tr>
        </thead>
        <tbody>
          <SectionHeader label="Demographics" />
          <Row label="Age, median (IQR)"
               value={fmtMedianIQR(d?.age_median, d?.age_q1, d?.age_q3, 'years')} />
          <Row label="Female, n (%)" value={fmt(d?.female_n, d?.female_pct)} />

          {rs && (rs.er_tested > 0 || rs.her2_tested > 0 || rs.tnbc_tested > 0) && (
            <>
              <SectionHeader label="Receptor Status" />
              {rs.er_tested > 0 && (
                <Row label={`ER Positive (n tested = ${rs.er_tested})`}
                     value={fmt(rs.er_positive_n, rs.er_positive_pct)} />
              )}
              {rs.her2_tested > 0 && (
                <Row label={`HER2 Positive (n tested = ${rs.her2_tested})`}
                     value={fmt(rs.her2_positive_n, rs.her2_positive_pct)} />
              )}
              {rs.tnbc_tested > 0 && (
                <Row label={`TNBC (n tested = ${rs.tnbc_tested})`}
                     value={fmt(rs.tnbc_n, rs.tnbc_pct)} />
              )}
            </>
          )}

          {stages && stages.length > 0 && (
            <>
              <SectionHeader label="Disease Stage" />
              {stages.map(s => (
                <Row key={s.stage} label={s.stage} value={fmt(s.n, s.pct)} />
              ))}
            </>
          )}

          {ecog && ecog.length > 0 && (
            <>
              <SectionHeader label="ECOG Performance Status" />
              {ecog.map(e => (
                <Row key={e.score} label={`ECOG ${e.score}`} value={fmt(e.n, e.pct)} />
              ))}
            </>
          )}

          {tx && (
            <>
              <SectionHeader label="Treatment Lines" />
              <Row label="Received 2nd-line therapy" value={fmt(tx.received_2l_n, tx.received_2l_pct)} />
              <Row label="Received 3rd-line+ therapy" value={fmt(tx.received_3l_n, tx.received_3l_pct)} />
            </>
          )}

          {mrd && mrd.tested > 0 && (
            <>
              <SectionHeader label={`MRD Status (n tested = ${mrd.tested})`} />
              <Row label="MRD Negative" value={fmt(mrd.negative_n, mrd.negative_pct)} />
              <Row label="MRD Positive"  value={fmt(mrd.positive_n,  mrd.positive_pct)} />
            </>
          )}

          {labs && (
            <>
              <SectionHeader label="Key Labs at Baseline" />
              {labs.hemoglobin_median != null && (
                <Row label="Hemoglobin, median (IQR)"
                     value={fmtMedianIQR(labs.hemoglobin_median, labs.hemoglobin_q1, labs.hemoglobin_q3, 'g/dL')} />
              )}
              {labs.creatinine_median != null && (
                <Row label="Creatinine, median (IQR)"
                     value={fmtMedianIQR(labs.creatinine_median, labs.creatinine_q1, labs.creatinine_q3, 'mg/dL')} />
              )}
              {labs.b2m_median != null && (
                <Row label="β2-Microglobulin, median (IQR)"
                     value={fmtMedianIQR(labs.b2m_median, labs.b2m_q1, labs.b2m_q3, 'mg/L')} />
              )}
            </>
          )}
        </tbody>
      </table>
      <p className="text-xs text-gray-400 mt-2 pl-3">Values shown as n (%) or median (IQR)</p>
    </div>
  )
}
