import { describe, it, expect } from 'vitest'
import { buildSeries, COHORT_COLORS, MAX_SERIES, mergeCategorySeries, pctOf, seriesKey } from '../cohortCompare'
import type { MetricsResponse } from '../../types'

const m = (count: number) => ({ cohort: { count } }) as unknown as MetricsResponse

describe('buildSeries', () => {
  it('puts the primary cohort first with the first color', () => {
    const s = buildSeries({ label: 'Current cohort', metrics: m(10) }, [{ id: 7, label: 'Saved', metrics: m(5) }])
    expect(s.map(x => x.key)).toEqual(['primary', 'saved:7'])
    expect(s[0].color).toBe(COHORT_COLORS[0])
    expect(s[1].color).toBe(COHORT_COLORS[1])
    expect(s[1].loading).toBe(false)
  })

  it('caps the series at five cohorts', () => {
    const comparisons = [1, 2, 3, 4, 5, 6].map(id => ({ id, label: `c${id}`, metrics: null, loading: true }))
    const s = buildSeries({ label: 'p', metrics: null }, comparisons)
    expect(s).toHaveLength(MAX_SERIES)
    expect(s[4].key).toBe('saved:4')
    expect(s[4].loading).toBe(true)
  })
})

describe('mergeCategorySeries', () => {
  it('keeps the first series order and appends categories only seen later', () => {
    const rows = mergeCategorySeries([
      [{ name: 'B', value: 1 }, { name: 'A', value: 2 }],
      [{ name: 'A', value: 3 }, { name: 'C', value: 4 }],
    ])
    expect(rows.map(r => r.name)).toEqual(['B', 'A', 'C'])
    expect(rows[1]).toEqual({ name: 'A', c0: 2, c1: 3 })
  })

  it('leaves a key unset when a series lacks the category or its value is null', () => {
    const rows = mergeCategorySeries([
      [{ name: 'X', value: 1 }],
      [{ name: 'X', value: null }, { name: 'Y', value: 9 }],
    ])
    expect(rows[0]).toEqual({ name: 'X', c0: 1 })
    expect(rows[1]).toEqual({ name: 'Y', c1: 9 })
    expect(seriesKey(2)).toBe('c2')
  })

  it('returns no rows for empty input', () => {
    expect(mergeCategorySeries([[], []])).toEqual([])
  })
})

describe('pctOf', () => {
  it('divides by the total and refuses a zero denominator', () => {
    expect(pctOf(1, 4)).toBe(25)
    expect(pctOf(1, 0)).toBeNull()
  })
})
