import { authHeaders } from '../utils/auth'
import { parseApiError, parseEventStream } from '../utils/errors'

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
  const response = await fetch(request.endpoint, request.options)

  if (!response.ok) {
    const errorPayload = await response.json()
    throw new Error(parseApiError(errorPayload))
  }

  return parseEventStream(response, onProgress)
}
