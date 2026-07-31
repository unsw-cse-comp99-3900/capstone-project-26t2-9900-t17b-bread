import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useArticleInputs } from './useArticleInputs'

describe('useArticleInputs', () => {
  it('tracks text input readiness and validation', () => {
    const setFormErrors = vi.fn()
    const { result } = renderHook(() =>
      useArticleInputs({
        minTextChars: 20,
        maxUploadSizeBytes: 10 * 1024 * 1024,
        onFormErrorsChange: setFormErrors,
      }),
    )

    act(() => {
      result.current.handleArticleAModeChange('text')
      result.current.handleArticleBModeChange('text')
      result.current.handleArticleATextChange({
        target: { value: 'This is enough article text for article A.' },
      })
      result.current.handleArticleBTextChange({
        target: { value: 'This is enough article text for article B.' },
      })
    })

    expect(result.current.canCompare).toBe(true)
    expect(result.current.validateInputs()).toEqual({
      articleA: '',
      articleB: '',
    })
  })

  it('clears one side of the input state', () => {
    const { result } = renderHook(() =>
      useArticleInputs({
        minTextChars: 20,
        maxUploadSizeBytes: 10 * 1024 * 1024,
        onFormErrorsChange: vi.fn(),
      }),
    )

    act(() => {
      result.current.handleArticleAUrlChange({
        target: { value: 'https://example.com/a' },
      })
    })
    expect(result.current.articleInputA.url).toBe('https://example.com/a')

    act(() => {
      result.current.clearArticleAInput()
    })
    expect(result.current.articleInputA.url).toBe('')
  })
})
