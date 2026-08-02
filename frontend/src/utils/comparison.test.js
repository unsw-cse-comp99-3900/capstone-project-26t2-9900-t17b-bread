import { describe, expect, it } from 'vitest'
import { formatReasonCode } from './comparison'

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
})
