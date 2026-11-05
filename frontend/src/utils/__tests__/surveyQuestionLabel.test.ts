import { describe, expect, it } from 'vitest'
import { questionLabel } from '../surveyQuestionLabel'

describe('questionLabel', () => {
  it('prefixes the questionnaire number when the key carries one', () => {
    expect(questionLabel({ number: '7a', text: 'Most recent treatment?' })).toBe('Q7a. Most recent treatment?')
  })

  it('returns the bare text without a number', () => {
    expect(questionLabel({ number: null, text: 'Country' })).toBe('Country')
    expect(questionLabel({ text: 'Country' })).toBe('Country')
  })
})
