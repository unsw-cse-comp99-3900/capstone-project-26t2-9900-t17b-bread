import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
})

window.HTMLElement.prototype.scrollIntoView = vi.fn()
window.requestAnimationFrame = (callback) => window.setTimeout(callback, 0)
window.cancelAnimationFrame = (id) => window.clearTimeout(id)

Object.defineProperty(navigator, 'clipboard', {
  configurable: true,
  value: {
    writeText: vi.fn().mockResolvedValue(undefined),
  },
})

URL.createObjectURL = vi.fn(() => 'blob:mock-download')
URL.revokeObjectURL = vi.fn()
