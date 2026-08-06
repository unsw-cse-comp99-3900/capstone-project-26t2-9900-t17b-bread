import { afterEach, describe, expect, it, vi } from 'vitest'
import { createCompareRequest, streamComparison } from './compareService'

describe('compareService', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

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

  it('stops comparisons that exceed the one minute limit', async () => {
    vi.useFakeTimers()
    global.fetch = vi.fn((_endpoint, options) =>
      new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => {
          reject(new DOMException('Aborted', 'AbortError'))
        })
      }),
    )

    const request = createCompareRequest({
      focus: 'general',
      authToken: '',
      articleA: {
        mode: 'text',
        text: 'Long article A text',
      },
      articleB: {
        mode: 'text',
        text: 'Long article B text',
      },
    })

    const expectation = expect(streamComparison(request, vi.fn())).rejects.toThrow(
      /too long/i,
    )
    await vi.advanceTimersByTimeAsync(60_000)

    await expectation
  })
})
