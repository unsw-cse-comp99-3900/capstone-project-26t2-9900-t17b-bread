import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  mockFrontendFetch,
  runTextComparison,
} from './test/appTestUtils'
import {
  comparisonPayload,
  irrelevantComparisonPayload,
} from './test/mockData'

describe('Narrative Diff comparison results', () => {
  beforeEach(() => {
    mockFrontendFetch()
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
    expect(screen.getByText(/13.7\/20/i)).toBeInTheDocument()
    expect(screen.getByText(/automatically selected factor/i)).toBeInTheDocument()
    expect(screen.getByText(/^political$/i)).toBeInTheDocument()
    expect(screen.getByText(/avg political relevance/i)).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /sort by/i })).toHaveValue(
      'best_match',
    )
    expect(screen.getByRole('checkbox', { name: /^Similar 1$/i })).toBeChecked()
    expect(
      screen.getByRole('checkbox', { name: /^Partially similar 1$/i }),
    ).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /^Divergent 1$/i })).toBeChecked()
  })

  it('shows a clear message when articles fail the relevance check', async () => {
    mockFrontendFetch({ comparisonPayload: irrelevantComparisonPayload })

    const user = await runTextComparison()

    const dialog = screen.getByRole('alertdialog')
    expect(
      within(dialog).getByText(/detailed comparison failed/i),
    ).toBeInTheDocument()
    expect(
      screen.getAllByText(/not relevant enough for detailed comparison/i).length,
    ).toBeGreaterThan(0)
    expect(
      screen.queryByRole('button', { name: /copy summary/i }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('combobox', { name: /sort by/i }),
    ).not.toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: /close/i }))

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
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
    const evidencePanel = screen.getByRole('complementary')
    expect(within(evidencePanel).getByText(/^reason$/i)).toBeInTheDocument()
    expect(
      within(evidencePanel).getByText(/similar content but use different wording/i),
    ).toBeInTheDocument()
    expect(within(evidencePanel).getByText(/match strength/i)).toBeInTheDocument()
    expect(within(evidencePanel).getAllByText(/18.0\/20/i).length).toBeGreaterThan(0)
    expect(
      within(evidencePanel).getByText(/stance discrepancy/i),
    ).toBeInTheDocument()
    expect(
      within(evidencePanel).getByText(/political relevance/i),
    ).toBeInTheDocument()
    expect(within(evidencePanel).getByText(/12.0\/20/i)).toBeInTheDocument()
    expect(
      within(evidencePanel).getByText(
        /selected once for the complete article pair/i,
      ),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /close evidence panel/i }))

    expect(
      screen.queryByText(/both paragraphs describe the same eruption/i),
    ).not.toBeInTheDocument()
  })

  it('filters highlighted relationships and restores them', async () => {
    const user = await runTextComparison()

    expect(
      screen.getByRole('button', {
        name: /a volcano erupted near the icelandic town/i,
      }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: /^Similar 1$/i }))

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

  it('uses backend-provided sorting options', async () => {
    const user = await runTextComparison()

    await user.selectOptions(
      screen.getByRole('combobox', { name: /sort by/i }),
      'most_divergent',
    )

    expect(screen.getByText(/pair 2/i)).toBeInTheDocument()
    expect(screen.getByText(/10.0\/20/i)).toBeInTheDocument()
  })

  it('sorts general-focus matches by the backend-selected global factor', async () => {
    const user = await runTextComparison()

    await user.selectOptions(
      screen.getByRole('combobox', { name: /sort by/i }),
      'selected_factor',
    )

    const evidencePanel = screen.getByRole('complementary')
    expect(within(evidencePanel).getByText(/pair 2/i)).toBeInTheDocument()
    expect(
      within(evidencePanel).getByText(/political relevance/i),
    ).toBeInTheDocument()
    expect(within(evidencePanel).getByText(/18.0\/20/i)).toBeInTheDocument()
  })

  it('shows the complete backend-provided factor score guide', async () => {
    const user = await runTextComparison()

    await user.click(screen.getByText(/political relevance guide/i))

    expect(
      screen.getByText(/automatically selected political factor/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/17-20: Very Strong/i)).toBeInTheDocument()
    expect(
      screen.getAllByText(/selected once for the complete article pair/i).length,
    ).toBeGreaterThan(0)
  })

  it('supports stored comparisons from the previous response shape', async () => {
    const legacyPayload = structuredClone(comparisonPayload)
    delete legacyPayload.comparison.selected_factor
    delete legacyPayload.comparison.summary.average_factor_relevance
    delete legacyPayload.comparison.score_guides.factor_relevance
    legacyPayload.comparison.sorting.options =
      legacyPayload.comparison.sorting.options.filter(
        (option) => option.key !== 'selected_factor',
      )
    legacyPayload.comparison.matches.forEach((match) => {
      delete match.factor_relevance
    })
    mockFrontendFetch({ comparisonPayload: legacyPayload })

    const user = await runTextComparison()
    await user.click(
      screen.getByRole('button', {
        name: /a volcano erupted near the icelandic town/i,
      }),
    )

    const evidencePanel = screen.getByRole('complementary')
    expect(within(evidencePanel).getByText(/match strength/i)).toBeInTheDocument()
    expect(
      within(evidencePanel).queryByText(/political relevance/i),
    ).not.toBeInTheDocument()
  })
})
