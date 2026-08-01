import { describe, expect, it } from 'vitest'
import { groupDemoSamples } from './demo'

describe('demo utilities', () => {
  it('groups demo samples by input type', () => {
    const groups = groupDemoSamples([
      { id: 'u', kind: 'url' },
      { id: 'p', kind: 'upload', articleA: { fileName: '1a.pdf' } },
      { id: 'w', kind: 'upload', articleA: { fileName: '1a.docx' } },
      { id: 't', kind: 'text' },
    ])

    expect(groups.find((group) => group.label === 'URL').samples).toHaveLength(1)
    expect(groups.find((group) => group.label === 'PDF').samples).toHaveLength(1)
    expect(groups.find((group) => group.label === 'Word').samples).toHaveLength(1)
    expect(groups.find((group) => group.label === 'Text').samples).toHaveLength(1)
  })
})
