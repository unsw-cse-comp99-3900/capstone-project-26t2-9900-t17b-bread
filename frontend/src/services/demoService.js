import { demoIndexPath } from '../config/appConfig'

export async function fetchDemoSamples() {
  const indexResponse = await fetch(demoIndexPath)

  if (!indexResponse.ok) {
    throw new Error('Demo index could not be loaded.')
  }

  const demoPaths = await indexResponse.json()
  return Promise.all(
    demoPaths.map(async (demoPath) => {
      const response = await fetch(demoPath)

      if (!response.ok) {
        throw new Error(`Demo metadata could not be loaded: ${demoPath}`)
      }

      return response.json()
    }),
  )
}
