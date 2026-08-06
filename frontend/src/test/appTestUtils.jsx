import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import App from '../App'
import {
  comparisonPayload,
  demoIndexResponse,
  demoMetadata,
  longArticleAText,
  longArticleBText,
} from './mockData'

export const routes = {
  health: '/health',
  demoIndex: '/demo-files/index.json',
  demoMetadata: '/demo-files/volcano-text/demo.json',
  demoTextA: '/demo-files/volcano-text/1a.txt',
  demoTextB: '/demo-files/volcano-text/1b.txt',
  compare: '/api/compare/stream',
  compareFiles: '/api/compare/files/stream',
  authMe: '/api/auth/me',
  authLogin: '/api/auth/login',
  authRegister: '/api/auth/register',
  history: '/api/history',
}

export function jsonResponse(data, ok = true) {
  return {
    ok,
    body: null,
    json: vi.fn().mockResolvedValue(data),
  }
}

export function textResponse(data, ok = true) {
  return {
    ok,
    text: vi.fn().mockResolvedValue(data),
  }
}

export function mockFrontendFetch({
  historyItems = [],
  comparisonPayload: nextComparisonPayload = comparisonPayload,
} = {}) {
  global.fetch = vi.fn((url, options = {}) => {
    if (url === routes.health) {
      return Promise.resolve(jsonResponse({ status: 'ok' }))
    }

    if (url === routes.authMe) {
      return Promise.resolve(
        jsonResponse({
          id: 1,
          email: 'tester@example.com',
          display_name: 'Tester',
        }),
      )
    }

    if (url === routes.authLogin || url === routes.authRegister) {
      return Promise.resolve(
        jsonResponse(
          {
            detail: [
              {
                msg: 'Username or password is incorrect.',
              },
            ],
          },
          false,
        ),
      )
    }

    if (url === routes.history && options.method === 'POST') {
      return Promise.resolve(jsonResponse({ item: null }))
    }

    if (url === routes.history) {
      return Promise.resolve(jsonResponse({ items: historyItems }))
    }

    if (url === routes.demoIndex) {
      return Promise.resolve(jsonResponse(demoIndexResponse))
    }

    if (url === routes.demoMetadata) {
      return Promise.resolve(jsonResponse(demoMetadata))
    }

    if (url === routes.demoTextA) {
      return Promise.resolve(textResponse(longArticleAText))
    }

    if (url === routes.demoTextB) {
      return Promise.resolve(textResponse(longArticleBText))
    }

    if (url === routes.compare || url === routes.compareFiles) {
      return Promise.resolve(jsonResponse(nextComparisonPayload))
    }

    return Promise.resolve(jsonResponse({}, false))
  })
}

export async function switchBothArticlesToText(user) {
  const sourceGroups = screen.getAllByLabelText(/article source type/i)

  for (const sourceGroup of sourceGroups) {
    await user.click(
      within(sourceGroup).getByRole('button', { name: /paste text/i }),
    )
  }
}

export async function runTextComparison() {
  const user = userEvent.setup()
  render(<App />)

  await switchBothArticlesToText(user)

  const textAreas = screen.getAllByPlaceholderText(/paste the full article text/i)
  fireEvent.change(textAreas[0], { target: { value: longArticleAText } })
  fireEvent.change(textAreas[1], { target: { value: longArticleBText } })
  await user.click(screen.getByRole('button', { name: /compare articles/i }))

  await screen.findByText('Volcano eruption forces evacuations')
  await screen.findByText('Reykjavik region faces lava disruption')

  return user
}

export function setLoggedInSession() {
  localStorage.setItem(
    'narrative-diff-auth',
    JSON.stringify({
      accessToken: 'test-token',
      user: {
        id: 1,
        email: 'tester@example.com',
        display_name: 'Tester',
      },
    }),
  )
}
