import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import App from './App'
import {
  longArticleAText,
  longArticleBText,
} from './test/mockData'
import {
  mockFrontendFetch,
  routes,
  switchBothArticlesToText,
} from './test/appTestUtils'

describe('Narrative Diff workflow', () => {
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
    expect(
      screen.queryByRole('button', { name: /history/i }),
    ).not.toBeInTheDocument()
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
})
