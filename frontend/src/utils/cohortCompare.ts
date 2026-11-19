import type { CohortSeries, MetricsResponse } from '../types'

/** The primary cohort plus up to four comparison cohorts. */
export const MAX_SERIES = 5
export const MAX_COMPARE_COHORTS = MAX_SERIES - 1

/** One fixed color per cohort slot; index 0 is the primary (Cohort Builder) cohort. */
export const COHORT_COLORS = ['#0d9488', '#2563eb', '#d97706', '#7c3aed', '#dc2626'] as const

export const PRIMARY_KEY = 'primary'

/** Recharts data key for the series at `index`. */
export function seriesKey(index: number): string {
  return `c${index}`
}

/**
 * Build the ordered list of cohorts to plot. The primary cohort is always
 * first; comparison cohorts keep the order in which they were selected.
 */
export function buildSeries(
  primary: { label: string; metrics: MetricsResponse | null },
  comparisons: { id: number; label: string; metrics: MetricsResponse | null; loading?: boolean }[],
): CohortSeries[] {
  const all = [
    { key: PRIMARY_KEY, label: primary.label, metrics: primary.metrics, loading: false },
    ...comparisons.slice(0, MAX_COMPARE_COHORTS).map(c => ({
      key: `saved:${c.id}`, label: c.label, metrics: c.metrics, loading: c.loading ?? false,
    })),
  ]
  return all.map((s, i) => ({ ...s, color: COHORT_COLORS[i % COHORT_COLORS.length] }))
}

export interface CategoryRow { name: string; value: number | null }

/**
 * Merge one list of (category, value) rows per series onto a shared category
 * axis for a grouped Recharts bar chart. Output rows are
 * `{ name, c0: value, c1: value, ... }` in first-seen category order, so the
 * primary cohort's ordering wins and categories seen only in a comparison
 * cohort are appended. A series that lacks a category leaves its key unset.
 */
export function mergeCategorySeries(
  series: CategoryRow[][],
): Record<string, string | number>[] {
  const order: string[] = []
  const byName = new Map<string, Record<string, string | number>>()
  series.forEach((rows, i) => {
    const key = seriesKey(i)
    for (const row of rows ?? []) {
      let point = byName.get(row.name)
      if (!point) {
        point = { name: row.name }
        byName.set(row.name, point)
        order.push(row.name)
      }
      if (row.value != null) point[key] = row.value
    }
  })
  return order.map(name => byName.get(name)!)
}

/** Percentage of `total`, or null when there is nothing to divide by. */
export function pctOf(count: number, total: number): number | null {
  return total > 0 ? (count / total) * 100 : null
}
