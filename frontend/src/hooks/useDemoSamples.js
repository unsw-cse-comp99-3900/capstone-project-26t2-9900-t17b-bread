import { useEffect, useState } from 'react'
import { fetchDemoSamples } from '../services/demoService'

export function useDemoSamples() {
  const [demoSamples, setDemoSamples] = useState([])
  const [demoLoadError, setDemoLoadError] = useState('')

  useEffect(() => {
    let isActive = true

    async function loadDemoIndex() {
      try {
        const samples = await fetchDemoSamples()

        if (isActive) {
          setDemoSamples(samples)
          setDemoLoadError('')
        }
      } catch (error) {
        if (isActive) {
          setDemoSamples([])
          setDemoLoadError(error.message)
        }
      }
    }

    loadDemoIndex()

    return () => {
      isActive = false
    }
  }, [])

  return { demoSamples, demoLoadError }
}
