import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import {
  comparisonPayload,
  demoIndexResponse,
  demoMetadata,
  longArticleAText,
  longArticleBText,
} from './test/mockData'

const routes = {
  health: '/health',
  demoIndex: '/demo-files/index.json',
  demoMetadata: '/demo-files/volcano-text/demo.json',
  demoTextA: '/demo-files/volcano-text/1a.txt',
  demoTextB: '/demo-files/volcano-text/1b.txt',
  compare: '/api/compare/stream',
  compareFiles: '/api/compare/files/stream',
  authMe: '/api/auth/me',
  history: '/api/history',
}

function jsonResponse(data, ok = true) {
  return {
    ok,
    body: null,
    json: vi.fn().mockResolvedValue(data),
  }
}

function textResponse(data, ok = true) {
  return {
    ok,
    text: vi.fn().mockResolvedValue(data),
  }
}

function mockFrontendFetch() {
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

    if (url === routes.history && options.method === 'POST') {
      return Promise.resolve(jsonResponse({ item: null }))
    }

    if (url === routes.history) {
      return Promise.resolve(jsonResponse({ items: [] }))
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
      return Promise.resolve(jsonResponse(comparisonPayload))
    }

    return Promise.resolve(jsonResponse({}, false))
  })
}

async function switchBothArticlesToText(user) {
  const sourceGroups = screen.getAllByLabelText(/article source type/i)

  for (const sourceGroup of sourceGroups) {
    await user.click(
      within(sourceGroup).getByRole('button', { name: /paste text/i }),
    )
  }
}

async function runTextComparison() {
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

describe('Narrative Diff frontend', () => {
  beforeEach(() => {
    mockFrontendFetch()
  })

  it('renders the main comparison workflow', async () => {
    render(<App />)

    expect(
      screen.getByRole('heading', {
        name: /how does the story change between news outlets/i,
      }),
    ).toBeInTheDocument()
    expect(screen.getByText(/try sample inputs/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /history/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /compare articles/i })).toBeDisabled()

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(routes.demoIndex)
    })
  })

  it('shows friendly validation when pasted text is too short', async () => {
    const user = userEvent.setup()
    render(<App />)

    await switchBothArticlesToText(user)

    const textAreas = screen.getAllByPlaceholderText(/paste the full article text/i)
    fireEvent.change(textAreas[0], { target: { value: 'Too short' } })
    fireEvent.change(textAreas[1], { target: { value: 'Also short' } })

    expect(
      screen.getByRole('button', { name: /compare articles/i }),
    ).toBeDisabled()
    expect(screen.getByText(/add two valid article sources/i)).toBeInTheDocument()
  })

  it('keeps compare disabled for invalid article URLs', async () => {
    render(<App />)

    const urlInputs = screen.getAllByPlaceholderText(
      /https:\/\/news-outlet.com\/article/i,
    )
    fireEvent.change(urlInputs[0], { target: { value: 'not-a-url' } })
    fireEvent.change(urlInputs[1], {
      target: { value: 'https://example.com/article' },
    })

    expect(
      screen.getByRole('button', { name: /compare articles/i }),
    ).toBeDisabled()
    expect(screen.getByText(/add two valid article sources/i)).toBeInTheDocument()
  })

  it('opens and closes the about dialog', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /about/i }))

    const dialog = screen.getByRole('dialog', { name: /narrative diff/i })
    expect(dialog).toBeInTheDocument()
    expect(
      within(dialog).getByText(/compares two reports on the same event/i),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /close about dialog/i }))

    expect(
      screen.queryByRole('dialog', { name: /narrative diff/i }),
    ).not.toBeInTheDocument()
  })

  it('loads a pasted-text demo pair into both article fields', async () => {
    const user = userEvent.setup()
    render(<App />)

    const textDemoSelect = await screen.findByRole('combobox', { name: /text/i })
    await user.selectOptions(textDemoSelect, 'volcano-text')

    expect(
      await screen.findByDisplayValue(new RegExp(longArticleAText.slice(0, 35))),
    ).toBeInTheDocument()
    expect(
      screen.getByDisplayValue(new RegExp(longArticleBText.slice(0, 35))),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/volcano text demo inputs loaded/i),
    ).toBeInTheDocument()
  })

  it('submits text input and displays paragraph-level highlights', async () => {
    await runTextComparison()

    expect(
      screen.getByText(
        /live comparison result loaded with the "general comparison" focus/i,
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/article difference overview/i)).toBeInTheDocument()
    expect(screen.getByText(/matched pairs/i)).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /^Aligned 1$/i })).toBeChecked()
    expect(
      screen.getByRole('checkbox', { name: /^Partially aligned 1$/i }),
    ).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /^Divergent 1$/i })).toBeChecked()
  })

  it('opens and closes the evidence panel from a highlighted paragraph', async () => {
    const user = await runTextComparison()

    await user.click(
      screen.getByRole('button', {
        name: /a volcano erupted near the icelandic town/i,
      }),
    )

    expect(screen.getByText(/pair 1/i)).toBeInTheDocument()
    expect(
      screen.getByText(/both paragraphs describe the same eruption/i),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /close evidence panel/i }))

    expect(
      screen.queryByText(/both paragraphs describe the same eruption/i),
    ).not.toBeInTheDocument()
  })

  it('filters highlighted relationships and restores them', async () => {
    const user = await runTextComparison()

    const alignedHighlight = screen.getByRole('button', {
      name: /a volcano erupted near the icelandic town/i,
    })
    expect(alignedHighlight).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: /^Aligned 1$/i }))

    expect(
      screen.queryByRole('button', {
        name: /a volcano erupted near the icelandic town/i,
      }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^reset$/i }))

    expect(
      screen.getByRole('button', {
        name: /a volcano erupted near the icelandic town/i,
      }),
    ).toBeInTheDocument()
  })

  it('copies the generated comparison summary', async () => {
    const user = await runTextComparison()
    const writeTextSpy = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockResolvedValue(undefined)

    await user.click(screen.getByRole('button', { name: /copy summary/i }))

    expect(writeTextSpy).toHaveBeenCalledWith(
      expect.stringContaining('Narrative Diff comparison summary'),
    )
    expect(
      screen.getByText(/comparison summary copied to clipboard/i),
    ).toBeInTheDocument()
  })

  it('downloads the current comparison result as an HTML report', async () => {
    const user = await runTextComparison()
    const anchorClick = vi.fn()
    const originalCreateElement = document.createElement.bind(document)

    vi.spyOn(document, 'createElement').mockImplementation((tagName, options) => {
      const element = originalCreateElement(tagName, options)

      if (tagName.toLowerCase() === 'a') {
        element.click = anchorClick
      }

      return element
    })

    await user.click(screen.getByRole('button', { name: /save result/i }))
    await user.click(screen.getByRole('button', { name: /download html report/i }))

    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(anchorClick).toHaveBeenCalled()
    expect(
      screen.getByText(/html report downloaded/i),
    ).toBeInTheDocument()
  })

  it('saves logged-in results to account history and downloads HTML', async () => {
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

    const user = await runTextComparison()
    const anchorClick = vi.fn()
    const originalCreateElement = document.createElement.bind(document)

    vi.spyOn(document, 'createElement').mockImplementation((tagName, options) => {
      const element = originalCreateElement(tagName, options)

      if (tagName.toLowerCase() === 'a') {
        element.click = anchorClick
      }

      return element
    })

    await user.click(screen.getByRole('button', { name: /save result/i }))

    expect(global.fetch).toHaveBeenCalledWith(
      routes.history,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ comparison_id: 42 }),
      }),
    )
    await user.click(screen.getByRole('button', { name: /download html report/i }))
    expect(anchorClick).toHaveBeenCalled()
    expect(
      screen.getByText(/html report downloaded/i),
    ).toBeInTheDocument()
  })

  it('switches the mobile article tab state', async () => {
    const user = await runTextComparison()
    const articleATab = screen.getByRole('button', { name: /^Article A$/i })
    const articleBTab = screen.getByRole('button', { name: /^Article B$/i })

    expect(articleATab).toHaveClass('active')
    expect(articleBTab).not.toHaveClass('active')

    await user.click(articleBTab)

    expect(articleATab).not.toHaveClass('active')
    expect(articleBTab).toHaveClass('active')
  })

  it('stores comparison history and can clear it', async () => {
    const user = await runTextComparison()

    expect(screen.getByRole('button', { name: /history1/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /history1/i }))
    const historyPanel = screen.getByRole('region', {
      name: /comparison history/i,
    })
    expect(
      within(historyPanel).getByText(/volcano eruption forces evacuations/i),
    ).toBeInTheDocument()

    await user.click(
      within(historyPanel).getByRole('button', { name: /clear history/i }),
    )
    expect(
      within(historyPanel).getByText(/your recent comparisons will appear/i),
    ).toBeInTheDocument()
  })
})
