import { useState } from 'react'
import { createCompareRequest, streamComparison } from '../services/compareService'
import {
  buildRelevanceNotice,
  getComparisonMatches,
  getCompareReadinessMessage,
  getDefaultSortKey,
  getFocusLabel,
  getInitialFilters,
  getSortingOptions,
  sortMatchesByBackendOption,
} from '../utils/comparison'

export function useComparison({
  articleInputA,
  articleInputB,
  authToken,
  canCompare,
  loadDemoSampleInputs,
  refreshAccountHistory,
  resetInputs,
  scrollToResults,
  setFormErrors,
  setIsHistoryOpen,
  setIsSaveOptionsOpen,
  setStatusMessage,
  validateInputs,
}) {
  const [focus, setFocus] = useState('general')
  const [apiErrors, setApiErrors] = useState([])
  const [progress, setProgress] = useState(null)
  const [articles, setArticles] = useState([])
  const [comparison, setComparison] = useState(null)
  const [comparisonId, setComparisonId] = useState(null)
  const [relevanceNotice, setRelevanceNotice] = useState(null)
  const [timeoutNotice, setTimeoutNotice] = useState(null)
  const [visibleLabels, setVisibleLabels] = useState(getInitialFilters)
  const [selectedMatchId, setSelectedMatchId] = useState(null)
  const [selectedSort, setSelectedSort] = useState('')
  const [activeMobileArticle, setActiveMobileArticle] = useState('A')
  const [isLoading, setIsLoading] = useState(false)

  function clearComparisonResult() {
    setArticles([])
    setComparison(null)
    setComparisonId(null)
    setRelevanceNotice(null)
    setTimeoutNotice(null)
    setSelectedMatchId(null)
    setSelectedSort('')
    setActiveMobileArticle('A')
    setApiErrors([])
    setProgress(null)
  }

  async function loadDemoSample(sample) {
    setIsLoading(true)
    setProgress(null)
    setArticles([])
    setComparison(null)
    setRelevanceNotice(null)
    setTimeoutNotice(null)
    setSelectedMatchId(null)
    setActiveMobileArticle('A')
    setApiErrors([])
    setFormErrors({})

    try {
      await loadDemoSampleInputs(sample)
      setStatusMessage(`${sample.label} demo inputs loaded. Click Compare articles to start.`)
    } catch (error) {
      setStatusMessage(`Could not load demo inputs. ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  function resetComparisonWorkspace() {
    resetInputs()
    setFormErrors({})
    setApiErrors([])
    setProgress(null)
    setArticles([])
    setComparison(null)
    setComparisonId(null)
    setRelevanceNotice(null)
    setTimeoutNotice(null)
    setVisibleLabels(getInitialFilters())
    setSelectedMatchId(null)
    setActiveMobileArticle('A')
    setIsSaveOptionsOpen(false)
  }

  function buildCompareRequest() {
    return createCompareRequest({
      focus,
      authToken,
      articleA: articleInputA,
      articleB: articleInputB,
    })
  }

  async function handleSubmit(event) {
    event.preventDefault()

    const nextFormErrors = validateInputs()

    Object.keys(nextFormErrors).forEach((fieldName) => {
      if (!nextFormErrors[fieldName]) {
        delete nextFormErrors[fieldName]
      }
    })

    setFormErrors(nextFormErrors)

    if (Object.keys(nextFormErrors).length > 0) {
      clearComparisonResult()
      setStatusMessage('')
      return
    }

    setIsLoading(true)
    setArticles([])
    setComparison(null)
    setComparisonId(null)
    setRelevanceNotice(null)
    setTimeoutNotice(null)
    setSelectedMatchId(null)
    setSelectedSort('')
    setActiveMobileArticle('A')
    setApiErrors([])
    setProgress({
      percent: 1,
      message: 'Starting comparison...',
      status: 'running',
    })
    setStatusMessage('Preparing comparison...')

    try {
      const request = buildCompareRequest()
      const data = await streamComparison(request, (progressEvent) => {
        setProgress({
          percent: progressEvent.percent ?? 0,
          message: progressEvent.message ?? 'Processing...',
          status: progressEvent.status ?? 'running',
        })
      })

      const returnedArticles = data.articles ?? []
      const returnedErrors = data.errors ?? []
      const backendComparison = data.comparison ?? null
      const backendRelevanceNotice = buildRelevanceNotice(data)
      const hasBackendMatches = getComparisonMatches(backendComparison).length > 0

      setArticles(returnedArticles)
      setApiErrors(returnedErrors)
      setComparison(backendComparison)
      setComparisonId(data.comparison_id ?? null)
      setRelevanceNotice(backendRelevanceNotice)
      setSelectedMatchId(null)
      setSelectedSort(getDefaultSortKey(backendComparison))
      setActiveMobileArticle('A')
      setProgress({
        percent: 100,
        message: data.processing?.message ?? 'Comparison finished.',
        status: 'completed',
      })

      if (returnedArticles.length > 0 && returnedErrors.length === 0) {
        if (backendRelevanceNotice) {
          setStatusMessage(backendRelevanceNotice.message)
        } else if (hasBackendMatches) {
          if (authToken) {
            await refreshAccountHistory(authToken)
          }
          setStatusMessage(
            `Live comparison result loaded with the "${getFocusLabel(data.focus)}" focus.`,
          )
        } else {
          setStatusMessage(
            'Article text loaded. No matched highlights were found yet.',
          )
        }
      } else if (returnedArticles.length > 0) {
        setStatusMessage(
          'Partial result loaded. One article could not be processed.',
        )
      } else {
        setStatusMessage('These articles could not be processed.')
      }

      if (returnedArticles.length > 0) {
        window.requestAnimationFrame(scrollToResults)
      }
    } catch (error) {
      clearComparisonResult()
      if (error.code === 'comparison_timeout') {
        setTimeoutNotice({
          eyebrow: 'Time limit reached',
          title: 'Comparison took too long',
          message:
            'The articles may be too long for one run. Please split them into smaller sections and try again.',
          action: 'Try comparing shorter sections of the articles.',
        })
      }
      setStatusMessage(`Could not complete the comparison. ${error.message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const articleA = articles.find((article) => article.article_ref === 'A')
  const articleB = articles.find((article) => article.article_ref === 'B')
  const comparisonMatches = getComparisonMatches(comparison)
  const sortingOptions = getSortingOptions(comparison)
  const activeSortingOption =
    sortingOptions.find((option) => option.key === selectedSort) ??
    sortingOptions.find((option) => option.key === getDefaultSortKey(comparison)) ??
    null
  const sortedComparisonMatches = sortMatchesByBackendOption(
    comparisonMatches,
    activeSortingOption,
  )
  const selectedMatch =
    sortedComparisonMatches.find((match) => match.id === selectedMatchId) ?? null
  const readinessMessage = getCompareReadinessMessage(canCompare, isLoading)

  function handleToggleLabel(label) {
    setVisibleLabels((currentLabels) => ({
      ...currentLabels,
      [label]: !currentLabels[label],
    }))
  }

  function handleResetFilters() {
    setVisibleLabels(getInitialFilters())
  }

  function handleSelectMatch(matchId) {
    setSelectedMatchId(matchId)
  }

  function handleSelectSort(nextSort) {
    setSelectedSort(nextSort)
    const nextSortingOption =
      sortingOptions.find((option) => option.key === nextSort) ?? null
    const nextMatches = sortMatchesByBackendOption(
      comparisonMatches,
      nextSortingOption,
    )
    setSelectedMatchId(nextMatches[0]?.id ?? null)

    if (nextMatches.length > 0) {
      window.requestAnimationFrame(scrollToResults)
    }
  }

  function handleRestoreHistory(item) {
    setArticles(item.articles ?? [])
    setComparison(item.comparison ?? null)
    setComparisonId(item.comparison_id ?? null)
    setRelevanceNotice(buildRelevanceNotice(item))
    setTimeoutNotice(null)
    setFocus(item.focus ?? 'general')
    setSelectedMatchId(null)
    setSelectedSort(getDefaultSortKey(item.comparison))
    setActiveMobileArticle('A')
    setVisibleLabels(getInitialFilters())
    setApiErrors([])
    setProgress(null)
    setStatusMessage(`Restored comparison from ${new Date(item.saved_at).toLocaleString()}.`)
    setIsHistoryOpen(false)

    if ((item.articles ?? []).length > 0) {
      window.requestAnimationFrame(scrollToResults)
    }
  }

  return {
    activeMobileArticle,
    apiErrors,
    articleA,
    articleB,
    articles,
    comparison,
    comparisonId,
    focus,
    handleResetFilters,
    handleRestoreHistory,
    handleSelectMatch,
    handleSelectSort,
    handleSubmit,
    handleToggleLabel,
    isLoading,
    loadDemoSample,
    progress,
    readinessMessage,
    relevanceNotice,
    timeoutNotice,
    setTimeoutNotice,
    resetComparisonWorkspace,
    selectedMatch,
    selectedMatchId,
    selectedSort,
    setActiveMobileArticle,
    setFocus,
    sortedComparisonMatches,
    sortingOptions,
    visibleLabels,
  }
}
