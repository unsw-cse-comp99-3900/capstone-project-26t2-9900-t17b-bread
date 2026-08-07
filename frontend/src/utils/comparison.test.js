import { describe, expect, it } from 'vitest'
import { formatFactorName, formatReasonCode } from './comparison'

describe('comparison utilities', () => {
  it('formats backend reason codes into user-facing explanations', () => {
    expect(formatReasonCode('related_content_with_nli_neutrality')).toBe(
      'The paragraphs discuss related content, but neither paragraph clearly supports or conflicts with the other.',
    )
    expect(formatReasonCode('strong_shared_content_with_additional_detail')).toBe(
      'The paragraphs share the same core content, while one side includes additional detail.',
    )
  })

  it('does not expose unknown technical reason codes', () => {
    expect(formatReasonCode('new_internal_reason_code')).toBe(
      'The comparison model matched these paragraphs based on their content.',
    )
  })

  it('formats backend factor identifiers for display', () => {
    expect(formatFactorName('political')).toBe('Political')
    expect(formatFactorName('social_impact')).toBe('Social Impact')
    expect(formatFactorName(null, 'Factor')).toBe('Factor')
  })
})
