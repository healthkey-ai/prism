import { useEffect, useRef, useState } from 'react'
import { fetchMetrics } from '../api/client'
import type { MetricsResponse, SavedCohort } from '../types'

export interface ComparisonResult {
  cohort: SavedCohort
  metrics: MetricsResponse | null
  loading: boolean
  error: string | null
}

type Entry = { metrics: MetricsResponse | null; loading: boolean; error: string | null }

function cacheKey(c: SavedCohort): string {
  return `${c.id}:${JSON.stringify(c.filters)}`
}

/**
 * Fetch dashboard metrics for each saved cohort selected for comparison.
 * Results are cached per cohort id + filters for the life of the hook, so
 * toggling a cohort off and on again does not refetch.
 */
export function useCohortComparison(cohorts: SavedCohort[]) {
  const [entries, setEntries] = useState<Record<string, Entry>>({})
  const inFlight = useRef(new Set<string>())
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  // Results are keyed by cohort, so a change in the selection must not cancel
  // fetches already in flight — a cohort toggled off and on again reuses them.
  useEffect(() => {
    for (const cohort of cohorts) {
      const key = cacheKey(cohort)
      // A failed fetch is retried the next time the selection changes.
      if ((entries[key] && !entries[key].error) || inFlight.current.has(key)) continue
      inFlight.current.add(key)
      setEntries(prev => ({ ...prev, [key]: { metrics: null, loading: true, error: null } }))
      fetchMetrics(cohort.filters)
        .then(metrics => {
          if (mounted.current) setEntries(prev => ({ ...prev, [key]: { metrics, loading: false, error: null } }))
        })
        .catch(() => {
          if (mounted.current) {
            setEntries(prev => ({ ...prev, [key]: { metrics: null, loading: false, error: 'Failed to load comparison cohort.' } }))
          }
        })
        .finally(() => inFlight.current.delete(key))
    }
    // `entries` is only read to skip cached keys; re-running on its change would be a no-op.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cohorts])

  const comparisons: ComparisonResult[] = cohorts.map(cohort => {
    const entry = entries[cacheKey(cohort)]
    return {
      cohort,
      metrics: entry?.metrics ?? null,
      loading: entry ? entry.loading : true,
      error: entry?.error ?? null,
    }
  })

  return {
    comparisons,
    anyLoading: comparisons.some(c => c.loading),
    anyError: comparisons.some(c => c.error),
  }
}
