import {
  clearHistory,
  deleteHistoryItem,
  saveHistoryEntry,
} from '../services/historyService'
import {
  copyTextToClipboard,
  downloadTextFile,
} from '../utils/appHelpers'
import {
  getMatchCounts,
  getMatchedText,
} from '../utils/comparison'
import { buildComparisonSummary, buildHtmlReport } from '../utils/exportReport'
import { isComparisonAlreadySaved } from '../utils/history'

export function useResultActions({
  articleA,
  articleB,
  articles,
  authToken,
  comparison,
  comparisonId,
  currentUser,
  focus,
  historyItems,
  refreshAccountHistory,
  selectedMatch,
  setHistoryItems,
  setIsSaveOptionsOpen,
  setStatusMessage,
  sortedComparisonMatches,
}) {
  async function handleClearHistory() {
    if (!authToken) {
      return
    }

    try {
      await clearHistory(authToken)
      setHistoryItems([])
      setStatusMessage('Account history cleared.')
    } catch (error) {
      setStatusMessage(`Could not clear account history. ${error.message}`)
    }
  }

  async function handleDeleteHistoryItem(itemId) {
    if (!authToken) {
      return
    }

    try {
      await deleteHistoryItem(authToken, itemId)
      await refreshAccountHistory(authToken)
      setStatusMessage('Saved comparison removed from account history.')
    } catch (error) {
      setStatusMessage(`Could not delete account history item. ${error.message}`)
    }
  }

  async function handleCopySummary() {
    if (!sortedComparisonMatches.length) {
      return
    }

    const summary = buildComparisonSummary({
      focus,
      articleA,
      articleB,
      matches: sortedComparisonMatches,
      selectedMatch,
    })
    await copyTextToClipboard(summary)
    setStatusMessage('Comparison summary copied to clipboard.')
  }

  async function saveCurrentResultToAccountHistory() {
    if (!authToken || !comparisonId) {
      return false
    }

    if (
      isComparisonAlreadySaved({
        historyItems,
        articleA,
        articleB,
        focus,
      })
    ) {
      return false
    }

    await saveHistoryEntry(authToken, comparisonId)
    await refreshAccountHistory(authToken)
    return true
  }

  async function handleOpenSaveOptions() {
    if (!articles.length && !comparison) {
      return
    }

    setIsSaveOptionsOpen(true)

    if (currentUser) {
      try {
        const didSave = await saveCurrentResultToAccountHistory()
        setStatusMessage(
          didSave
            ? 'Comparison saved to your account history.'
            : 'This comparison is already saved in your history.',
        )
      } catch (error) {
        setStatusMessage(`Could not save to account history. ${error.message}`)
      }
    }
  }

  function handleDownloadHtmlReport() {
    if (!articles.length && !comparison) {
      return
    }

    const savedAt = new Date().toISOString()
    const enrichedMatches = sortedComparisonMatches.map((match) => ({
      ...match,
      articleAText: getMatchedText(articleA, match, 'A'),
      articleBText: getMatchedText(articleB, match, 'B'),
    }))
    const htmlReport = buildHtmlReport({
      focus,
      articleA,
      articleB,
      matches: enrichedMatches,
      counts: getMatchCounts(sortedComparisonMatches),
      summary: comparison?.summary,
      scoreGuides: comparison?.score_guides,
      generatedAt: savedAt,
    })
    const datePart = savedAt.slice(0, 10)
    downloadTextFile(
      htmlReport,
      `comparison-report-${datePart}.html`,
      'text/html',
    )
    setIsSaveOptionsOpen(false)
    setStatusMessage(
      currentUser
        ? 'HTML report downloaded. This comparison is also saved in account history.'
        : 'HTML report downloaded. Log in to save comparisons to account history.',
    )
  }

  return {
    handleClearHistory,
    handleCopySummary,
    handleDeleteHistoryItem,
    handleDownloadHtmlReport,
    handleOpenSaveOptions,
  }
}
