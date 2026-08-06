import { useEffect, useRef, useState } from 'react'
import { checkBackendHealth } from '../services/healthService'

export function useBackendStatus(isLoading) {
  const [backendStatus, setBackendStatus] = useState('offline')
  const backendFailureCountRef = useRef(0)
  const isLoadingRef = useRef(isLoading)

  useEffect(() => {
    isLoadingRef.current = isLoading
  }, [isLoading])

  useEffect(() => {
    let isActive = true
    let timeoutId

    async function checkBackendStatus() {
      const controller = new AbortController()
      timeoutId = window.setTimeout(() => controller.abort(), 3500)

      try {
        await checkBackendHealth(controller.signal)

        if (isActive) {
          backendFailureCountRef.current = 0
          setBackendStatus('online')
        }
      } catch {
        if (isActive) {
          backendFailureCountRef.current += 1
          if (backendFailureCountRef.current >= 3 && !isLoadingRef.current) {
            setBackendStatus('offline')
          }
        }
      } finally {
        window.clearTimeout(timeoutId)
      }
    }

    checkBackendStatus()
    const intervalId = window.setInterval(checkBackendStatus, 30000)

    return () => {
      isActive = false
      window.clearTimeout(timeoutId)
      window.clearInterval(intervalId)
    }
  }, [])

  return backendStatus
}
