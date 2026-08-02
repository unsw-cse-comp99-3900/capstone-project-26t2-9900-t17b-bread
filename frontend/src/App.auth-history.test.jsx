import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { comparisonPayload } from './test/mockData'
import {
  mockFrontendFetch,
  routes,
  runTextComparison,
  setLoggedInSession,
} from './test/appTestUtils'

describe('Narrative Diff auth and history', () => {
  beforeEach(() => {
    mockFrontendFetch()
  })

  it('saves logged-in results to account history and downloads HTML', async () => {
    setLoggedInSession()

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

  it('does not save the same article pair and focus twice', async () => {
    setLoggedInSession()
    mockFrontendFetch({
      historyItems: [
        {
          id: 7,
          comparison_id: 100,
          focus: 'general',
          articles: comparisonPayload.articles,
          comparison: comparisonPayload.comparison,
        },
      ],
    })

    const user = await runTextComparison()
    await user.click(screen.getByRole('button', { name: /save result/i }))

    expect(global.fetch).not.toHaveBeenCalledWith(
      routes.history,
      expect.objectContaining({ method: 'POST' }),
    )
    expect(
      screen.getByText(/already saved in your history/i),
    ).toBeInTheDocument()
  })

  it('scrolls to the comparison view after restoring a saved result', async () => {
    setLoggedInSession()
    mockFrontendFetch({
      historyItems: [
        {
          id: 7,
          comparison_id: 100,
          focus: 'general',
          label:
            'A volcano erupted near the Icelandic fishing town of Grindavik vs An eruption near Reykjavik forced Icelandic authorities',
          saved_at: '2026-08-02T00:00:00.000Z',
          articles: comparisonPayload.articles,
          comparison: comparisonPayload.comparison,
        },
      ],
    })

    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Tester')
    await user.click(screen.getByRole('button', { name: /history/i }))
    const historyPanel = screen.getByRole('region', {
      name: /comparison history/i,
    })
    const [historyItemButton] = within(historyPanel).getAllByRole('button', {
      name: /volcano erupted/i,
    })
    await user.click(historyItemButton)

    await waitFor(() => {
      expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled()
    })
  })

  it('shows specific login errors returned by the backend', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /login/i }))

    const dialog = screen.getByRole('dialog', { name: /log in/i })
    await user.type(within(dialog).getByLabelText(/username/i), 'MercuryWang76')
    await user.type(within(dialog).getByLabelText(/password/i), 'wrongpass')
    await user.click(within(dialog).getByRole('button', { name: /^log in$/i }))

    expect(
      await within(dialog).findByText(/username or password is incorrect/i),
    ).toBeInTheDocument()
    expect(
      within(dialog).queryByText(/request could not be completed/i),
    ).not.toBeInTheDocument()
  })

  it('clears article inputs when the user logs out', async () => {
    setLoggedInSession()

    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('Tester')

    const urlInputs = screen.getAllByPlaceholderText(
      /https:\/\/news-outlet.com\/article/i,
    )
    await user.type(urlInputs[0], 'https://example.com/article-a')
    await user.type(urlInputs[1], 'https://example.com/article-b')

    await user.click(screen.getByRole('button', { name: /logout/i }))

    await waitFor(() => {
      expect(urlInputs[0]).toHaveValue('')
      expect(urlInputs[1]).toHaveValue('')
    })
    expect(screen.getByText(/^logged out\.$/i)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /history/i }),
    ).not.toBeInTheDocument()
  })

  it('keeps history hidden for logged-out comparisons', async () => {
    await runTextComparison()

    expect(
      screen.queryByRole('button', { name: /history/i }),
    ).not.toBeInTheDocument()
  })
})
