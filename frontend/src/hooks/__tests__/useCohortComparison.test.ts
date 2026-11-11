import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useCohortComparison } from '../useCohortComparison'
import * as client from '../../api/client'
import type { MetricsResponse, SavedCohort } from '../../types'

vi.mock('../../api/client', () => ({ fetchMetrics: vi.fn() }))

const cohort = (id: number): SavedCohort => ({
  id, name: `c${id}`, description: '', filters: { disease: 'Multiple Myeloma', stage: [`S${id}`] },
  created_at: '', updated_at: '',
})
const metrics = (count: number) => ({ cohort: { count } }) as unknown as MetricsResponse

describe('useCohortComparison', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches metrics once per cohort with that cohort’s filters', async () => {
    vi.mocked(client.fetchMetrics).mockImplementation(async f => metrics(f.stage?.[0] === 'S1' ? 1 : 2))
    const { result } = renderHook(() => useCohortComparison([cohort(1), cohort(2)]))
    expect(result.current.anyLoading).toBe(true)
    await waitFor(() => expect(result.current.anyLoading).toBe(false))
    expect(client.fetchMetrics).toHaveBeenCalledTimes(2)
    expect(client.fetchMetrics).toHaveBeenCalledWith(cohort(1).filters)
    expect(result.current.comparisons.map(c => c.metrics?.cohort.count)).toEqual([1, 2])
  })

  it('does not refetch a cohort that is toggled off and on again', async () => {
    vi.mocked(client.fetchMetrics).mockResolvedValue(metrics(3))
    const { result, rerender } = renderHook(({ cohorts }) => useCohortComparison(cohorts), {
      initialProps: { cohorts: [cohort(1)] },
    })
    await waitFor(() => expect(result.current.anyLoading).toBe(false))
    rerender({ cohorts: [] })
    expect(result.current.comparisons).toEqual([])
    rerender({ cohorts: [cohort(1)] })
    expect(result.current.anyLoading).toBe(false)
    expect(result.current.comparisons[0].metrics?.cohort.count).toBe(3)
    expect(client.fetchMetrics).toHaveBeenCalledTimes(1)
  })

  it('reports an error for a cohort whose fetch fails without blocking the others', async () => {
    vi.mocked(client.fetchMetrics)
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce(metrics(4))
    const { result } = renderHook(() => useCohortComparison([cohort(1), cohort(2)]))
    await waitFor(() => expect(result.current.anyLoading).toBe(false))
    expect(result.current.anyError).toBe(true)
    expect(result.current.comparisons[0].error).toMatch(/Failed/)
    expect(result.current.comparisons[0].metrics).toBeNull()
    expect(result.current.comparisons[1].metrics?.cohort.count).toBe(4)
  })
})
