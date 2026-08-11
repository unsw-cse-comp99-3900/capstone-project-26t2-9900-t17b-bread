import { friendlyErrorMessages } from '../config/appConfig'

export function getFriendlyError(error) {
  return (
    friendlyErrorMessages[error?.code] ?? {
      title: 'Article could not be loaded',
      message:
        error?.message ??
        'Something went wrong while trying to process this article.',
      action: 'Check the link and try again, or use another source.',
    }
  )
}

export function parseApiError(errorPayload) {
  if (typeof errorPayload?.detail === 'string') {
    return errorPayload.detail
  }

  return (
    errorPayload?.detail?.message ??
    errorPayload?.error?.message ??
    'The comparison could not be completed.'
  )
}

export function createApiError(message, code) {
  const error = new Error(message)
  if (code) {
    error.code = code
  }
  return error
}

export async function parseEventStream(response, onProgress) {
  const reader = response.body?.getReader()
  if (!reader) {
    return response.json()
  }

  const decoder = new TextDecoder()
  // A network chunk may end in the middle of an SSE message, so keep the remainder.
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const chunk of chunks) {
      const lines = chunk.split('\n')
      const eventLine = lines.find((line) => line.startsWith('event:'))
      const dataLine = lines.find((line) => line.startsWith('data:'))

      if (!eventLine || !dataLine) {
        continue
      }

      const event = eventLine.replace('event:', '').trim()
      let data

      try {
        data = JSON.parse(dataLine.replace('data:', '').trim())
      } catch {
        throw new Error(
          'The comparison service returned an unexpected progress update. Please try again.',
        )
      }

      if (event === 'progress') {
        onProgress(data)
      }

      if (event === 'error') {
        throw createApiError(
          data?.message ?? 'The comparison could not be completed.',
          data?.code,
        )
      }

      if (event === 'result') {
        return data
      }
    }
  }

  throw new Error('The comparison ended before returning a result.')
}

export function clearFieldError(errors, fieldName) {
  if (!errors[fieldName]) {
    return errors
  }

  const nextErrors = { ...errors }
  delete nextErrors[fieldName]
  return nextErrors
}

