export async function parseJsonResponse(response) {
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(parseResponseErrorMessage(payload))
  }
  return payload
}

export function parseResponseErrorMessage(payload) {
  const detail = payload?.detail

  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => item?.msg ?? item?.message)
      .filter(Boolean)

    if (messages.length > 0) {
      return messages.join(' ')
    }
  }

  if (typeof detail?.message === 'string') {
    return detail.message
  }

  if (typeof payload?.message === 'string') {
    return payload.message
  }

  return 'The request could not be completed.'
}
