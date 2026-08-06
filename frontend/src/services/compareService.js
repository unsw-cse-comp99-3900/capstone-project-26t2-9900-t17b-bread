import { authHeaders } from '../utils/auth'
import { parseResponseErrorMessage } from '../utils/api'
import { createApiError, parseApiError, parseEventStream } from '../utils/errors'

const COMPARISON_TIMEOUT_MS = 60_000
const COMPARISON_TIMEOUT_MESSAGE =
  'This comparison is taking too long. The articles may be too long for one run. Please split them into smaller sections and try again.'

export function createCompareRequest({ focus, authToken, articleA, articleB }) {
  const usesUpload = articleA.mode === 'upload' || articleB.mode === 'upload'

  if (!usesUpload) {
    const body = { focus }

    if (articleA.mode === 'text') {
      body.article_a_text = articleA.text.trim()
    } else {
      body.article_a_url = articleA.url.trim()
    }

    if (articleB.mode === 'text') {
      body.article_b_text = articleB.text.trim()
    } else {
      body.article_b_url = articleB.url.trim()
    }

    return {
      endpoint: '/api/compare/stream',
      options: {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(authToken),
        },
        body: JSON.stringify(body),
      },
    }
  }

  const formData = new FormData()
  formData.append('focus', focus)

  if (articleA.mode === 'url') {
    formData.append('article_a_url', articleA.url.trim())
  } else if (articleA.mode === 'text') {
    formData.append('article_a_text', articleA.text.trim())
  } else {
    formData.append('article_a_file', articleA.file)
  }

  if (articleB.mode === 'url') {
    formData.append('article_b_url', articleB.url.trim())
  } else if (articleB.mode === 'text') {
    formData.append('article_b_text', articleB.text.trim())
  } else {
    formData.append('article_b_file', articleB.file)
  }

  return {
    endpoint: '/api/compare/files/stream',
    options: {
      method: 'POST',
      headers: authHeaders(authToken),
      body: formData,
    },
  }
}

export async function streamComparison(request, onProgress) {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => {
    controller.abort()
  }, COMPARISON_TIMEOUT_MS)

  try {
    const response = await fetch(request.endpoint, {
      ...request.options,
      signal: controller.signal,
    })

    if (!response.ok) {
      const text = await response.text()
      let errorPayload = null

      try {
        errorPayload = JSON.parse(text)
      } catch {
        throw createApiError(
          'The comparison service returned an unexpected result. Please try again, or check that the service is running.',
        )
      }

      throw createApiError(
        parseApiError(errorPayload) || parseResponseErrorMessage(errorPayload),
        errorPayload?.detail?.code ?? errorPayload?.code,
      )
    }

    return await parseEventStream(response, onProgress)
  } catch (error) {
    if (error.name === 'AbortError') {
      throw createApiError(COMPARISON_TIMEOUT_MESSAGE, 'comparison_timeout')
    }
    throw error
  } finally {
    window.clearTimeout(timeoutId)
  }
}
