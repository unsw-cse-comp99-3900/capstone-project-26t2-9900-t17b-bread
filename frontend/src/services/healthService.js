export async function checkBackendHealth(signal) {
  const response = await fetch('/health', {
    cache: 'no-store',
    signal,
  })

  if (!response.ok) {
    throw new Error('Backend health check failed.')
  }

  return response
}
