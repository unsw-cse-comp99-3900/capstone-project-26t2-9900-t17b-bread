import { describe, expect, it } from 'vitest'
import { createCompareRequest } from './compareService'

describe('compareService', () => {
  it('creates a JSON compare request for URL and pasted text inputs', () => {
    const request = createCompareRequest({
      focus: 'general',
      authToken: 'token-1',
      articleA: {
        mode: 'url',
        url: 'https://example.com/a',
        text: '',
      },
      articleB: {
        mode: 'text',
        url: '',
        text: 'Long pasted article text',
      },
    })

    expect(request.endpoint).toBe('/api/compare/stream')
    expect(request.options.headers.Authorization).toBe('Bearer token-1')
    expect(JSON.parse(request.options.body)).toEqual({
      focus: 'general',
      article_a_url: 'https://example.com/a',
      article_b_text: 'Long pasted article text',
    })
  })

  it('creates a file compare request when either side is uploaded', () => {
    const file = new File(['hello'], 'article.pdf', { type: 'application/pdf' })
    const request = createCompareRequest({
      focus: 'general',
      authToken: 'token-1',
      articleA: {
        mode: 'upload',
        file,
      },
      articleB: {
        mode: 'url',
        url: 'https://example.com/b',
      },
    })

    expect(request.endpoint).toBe('/api/compare/files/stream')
    expect(request.options.headers.Authorization).toBe('Bearer token-1')
    expect(request.options.body.get('article_a_file')).toBe(file)
    expect(request.options.body.get('article_b_url')).toBe('https://example.com/b')
  })
})
