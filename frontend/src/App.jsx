import { useEffect, useRef, useState } from 'react'
import {
  focusOptions,
  maxUploadSizeBytes,
  minTextChars,
} from './config/appConfig'
import { AuthModal, HistoryPanel, SaveOptionsModal } from './components/AccountPanels'
import { ArticleSourceField } from './components/ArticleInputs'
import { ArticlePanel } from './components/ArticlePanel'
import {
  ComparisonControls,
  ComparisonSummaryCard,
  SortingControl,
} from './components/ComparisonResults'
import { MatchExplanationPanel } from './components/MatchExplanationPanel'
import { useArticleInputs } from './hooks/useArticleInputs'
import { useAuth } from './hooks/useAuth'
import { useBackendStatus } from './hooks/useBackendStatus'
import { useComparison } from './hooks/useComparison'
import { useDemoSamples } from './hooks/useDemoSamples'
import {
  copyTextToClipboard,
  downloadTextFile,
} from './utils/appHelpers'
import { groupDemoSamples } from './utils/demo'
import { buildHtmlReport, buildComparisonSummary } from './utils/exportReport'
import {
  getErrorForArticle,
  getMatchCounts,
  getMatchedText,
} from './utils/comparison'
import { isComparisonAlreadySaved } from './utils/history'
import {
  clearHistory,
  deleteHistoryItem,
  saveHistoryEntry,
} from './services/historyService'
import './styles/index.css'

function App() {
  const [formErrors, setFormErrors] = useState({})
  const [statusMessage, setStatusMessage] = useState('')
  const [historyItems, setHistoryItems] = useState([])
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [isSaveOptionsOpen, setIsSaveOptionsOpen] = useState(false)
  const [isAboutOpen, setIsAboutOpen] = useState(false)
  const [showBackToTop, setShowBackToTop] = useState(false)
  const {
    articleInputA,
    articleInputB,
    canCompare,
    handleArticleAModeChange,
    handleArticleBModeChange,
    handleArticleAUrlChange,
    handleArticleBUrlChange,
    handleArticleATextChange,
    handleArticleBTextChange,
    handleArticleAFileChange,
    handleArticleBFileChange,
    clearArticleAInput,
    clearArticleBInput,
    resetInputs,
    loadDemoSampleInputs,
    convertArticleAToWord,
    convertArticleBToWord,
    validateInputs,
  } = useArticleInputs({
    minTextChars,
    maxUploadSizeBytes,
    onFormErrorsChange: setFormErrors,
  })
  const { demoSamples, demoLoadError } = useDemoSamples()
  const resultsSectionRef = useRef(null)
  const comparisonResetRef = useRef(null)
  const {
    authToken,
    currentUser,
    isAuthOpen,
    setIsAuthOpen,
    authMode,
    setAuthMode,
    authForm,
    setAuthForm,
    authError,
    setAuthError,
    isAuthSubmitting,
    refreshAccountHistory,
    handleAuthSubmit,
    handleLogout,
  } = useAuth({
    onHistoryItemsChange: setHistoryItems,
    onWorkspaceReset: () => comparisonResetRef.current?.(),
    onHistoryClose: () => setIsHistoryOpen(false),
    onStatusMessage: setStatusMessage,
  })
  const {
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
    resetComparisonWorkspace,
    selectedMatch,
    selectedMatchId,
    selectedSort,
    setActiveMobileArticle,
    setFocus,
    sortedComparisonMatches,
    sortingOptions,
    visibleLabels,
  } = useComparison({
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
  })
  const backendStatus = useBackendStatus(isLoading)
  comparisonResetRef.current = resetComparisonWorkspace
  useEffect(() => {
    function handleWindowScroll() {
      setShowBackToTop(window.scrollY > 520)
    }

    handleWindowScroll()
    window.addEventListener('scroll', handleWindowScroll, { passive: true })

    return () => window.removeEventListener('scroll', handleWindowScroll)
  }, [])

  const demoGroups = groupDemoSamples(demoSamples)

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

  function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function scrollToResults() {
    resultsSectionRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
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

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="Narrative Diff home">
          <img
            className="brand-logo"
            src="/narrative-diff-icon.svg"
            alt=""
            aria-hidden="true"
          />
          <span>Narrative Diff</span>
        </a>
        <div className="header-actions">
          {currentUser ? (
            <>
              <button
                className="history-button"
                type="button"
                onClick={() => setIsHistoryOpen((isOpen) => !isOpen)}
              >
                History
                {historyItems.length > 0 && <span>{historyItems.length}</span>}
              </button>
              <span className="user-pill">
                {currentUser.display_name || currentUser.username}
              </span>
              <button
                className="header-pill-button"
                type="button"
                onClick={handleLogout}
              >
                Logout
              </button>
            </>
          ) : (
            <button
              className="header-pill-button"
              type="button"
              onClick={() => {
                setAuthMode('login')
                setAuthError('')
                setIsAuthOpen(true)
              }}
            >
              Login
            </button>
          )}
          <button
            className="header-pill-button"
            type="button"
            onClick={() => setIsAboutOpen(true)}
          >
            About
          </button>
          <span className="sprint-label">Sprint 3 prototype</span>
        </div>
      </header>

      <span
        className={`backend-status backend-status--${backendStatus}`}
        aria-label={`Backend ${backendStatus}`}
        title={`Backend ${backendStatus}`}
      />

      {isAboutOpen && (
        <div
          className="about-modal-backdrop"
          role="presentation"
          onMouseDown={() => setIsAboutOpen(false)}
        >
          <section
            className="about-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="about-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="about-modal__header">
              <div>
                <p className="eyebrow">About</p>
                <h2 id="about-title">Narrative Diff</h2>
              </div>
              <button
                className="about-modal__close"
                type="button"
                onClick={() => setIsAboutOpen(false)}
                aria-label="Close about dialog"
              >
                x
              </button>
            </div>
            <p>
              Narrative Diff compares two reports on the same event and shows
              where their paragraph-level evidence aligns, partially aligns, or
              diverges.
            </p>
            <p>
              You can enter article URLs, paste text directly, or upload
              supported documents. The highlighted results include matched
              paragraph pairs, relationship labels, 0-20 scores, and
              explanations from the backend comparison pipeline.
            </p>
            <p>
              Logged-in users can save comparison history to the database and
              reopen previous results from the History panel.
            </p>
          </section>
        </div>
      )}

      <AuthModal
        isOpen={isAuthOpen}
        mode={authMode}
        authForm={authForm}
        error={authError}
        isSubmitting={isAuthSubmitting}
        onClose={() => setIsAuthOpen(false)}
        onModeChange={(nextMode) => {
          setAuthMode(nextMode)
          setAuthError('')
        }}
        onFormChange={setAuthForm}
        onSubmit={handleAuthSubmit}
      />

      <SaveOptionsModal
        isOpen={isSaveOptionsOpen}
        currentUser={currentUser}
        onClose={() => setIsSaveOptionsOpen(false)}
        onDownloadHtml={handleDownloadHtmlReport}
      />

      <main>
        {currentUser && (
          <HistoryPanel
            historyItems={historyItems}
            isOpen={isHistoryOpen}
            onClose={() => setIsHistoryOpen(false)}
            onRestore={handleRestoreHistory}
            onDelete={handleDeleteHistoryItem}
            onClear={handleClearHistory}
          />
        )}

        <section className="hero-section">
          <p className="eyebrow">Compare reporting. See the difference.</p>
          <h1>How does the story change between news outlets?</h1>
          <p className="hero-copy">
            Compare two reports on the same story and see where they align,
            diverge, or leave details out.
          </p>

          <div className="demo-prompt">
            <div className="demo-prompt__copy">
              <strong>Try sample inputs</strong>
            </div>
            <div className="demo-buttons" aria-label="Demo input examples">
              {demoSamples.length > 0 ? (
                <>
                  {demoGroups
                    .filter((group) => group.samples.length > 0)
                    .map((group) => (
                    <label className="demo-select-label" key={group.label}>
                      {group.label}
                      <select
                        className="demo-select"
                        value=""
                        onChange={(event) => {
                          const selectedSample = group.samples.find(
                            (sample) => sample.id === event.target.value,
                          )
                          if (selectedSample) {
                            loadDemoSample(selectedSample)
                          }
                        }}
                        disabled={isLoading || group.samples.length === 0}
                      >
                        <option value="" disabled>
                          Choose pair
                        </option>
                        {group.samples.map((sample) => (
                          <option key={sample.id} value={sample.id}>
                            {sample.shortLabel ?? sample.description}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                </>
              ) : (
                <span className="demo-load-status">
                  {demoLoadError || 'Loading demo inputs...'}
                </span>
              )}
            </div>
          </div>

          <form className="compare-form" onSubmit={handleSubmit} noValidate>
            <div className="url-fields">
              <ArticleSourceField
                side="A"
                title="First article"
                mode={articleInputA.mode}
                url={articleInputA.url}
                text={articleInputA.text}
                file={articleInputA.file}
                pdfInfo={articleInputA.pdfInfo}
                wordStatus={articleInputA.wordStatus}
                error={formErrors.articleA}
                isLoading={isLoading}
                onModeChange={handleArticleAModeChange}
                onUrlChange={handleArticleAUrlChange}
                onTextChange={handleArticleATextChange}
                onFileChange={handleArticleAFileChange}
                onConvertWord={convertArticleAToWord}
                onClear={clearArticleAInput}
              />

              <ArticleSourceField
                side="B"
                title="Second article"
                mode={articleInputB.mode}
                url={articleInputB.url}
                text={articleInputB.text}
                file={articleInputB.file}
                pdfInfo={articleInputB.pdfInfo}
                wordStatus={articleInputB.wordStatus}
                error={formErrors.articleB}
                isLoading={isLoading}
                onModeChange={handleArticleBModeChange}
                onUrlChange={handleArticleBUrlChange}
                onTextChange={handleArticleBTextChange}
                onFileChange={handleArticleBFileChange}
                onConvertWord={convertArticleBToWord}
                onClear={clearArticleBInput}
              />
            </div>

            <div className="form-actions">
              <div className="focus-field">
                <label htmlFor="comparison-focus">Comparison focus</label>
                <select
                  id="comparison-focus"
                  value={focus}
                  onChange={(event) => setFocus(event.target.value)}
                  disabled={isLoading}
                >
                  {focusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <button
                className="compare-button"
                type="submit"
                disabled={isLoading || !canCompare}
              >
                {isLoading ? 'Comparing...' : 'Compare articles'}
                <span aria-hidden="true">-&gt;</span>
              </button>
            </div>

            {readinessMessage && (
              <p className="compare-readiness">{readinessMessage}</p>
            )}

            {statusMessage && (
              <p
                className={`status-message${articles.length ? ' status-message--success' : ''}`}
                role="status"
              >
                {statusMessage}
              </p>
            )}

            {progress && (
              <div className="progress-panel" role="status" aria-live="polite">
                <div className="progress-panel__meta">
                  <span>{progress.message}</span>
                  <strong>{Math.round(progress.percent)}%</strong>
                </div>
                <div className="progress-track" aria-hidden="true">
                  <span style={{ width: `${Math.min(progress.percent, 100)}%` }} />
                </div>
              </div>
            )}

          </form>
        </section>

        <section
          className="results-section"
          aria-labelledby="results-title"
          ref={resultsSectionRef}
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">Comparison view</p>
              <h2 id="results-title">Matched article evidence</h2>
            </div>
            <div className="section-heading__actions">
              <p>
                Review the source text and inspect highlighted similarities or
                differences.
              </p>
              <button
                className="save-results-button"
                type="button"
                onClick={handleOpenSaveOptions}
                disabled={!articles.length && !comparison}
              >
                Save result
              </button>
              <div className="section-button-row">
                <button
                  className="save-results-button"
                  type="button"
                  onClick={handleCopySummary}
                  disabled={!sortedComparisonMatches.length}
                >
                  Copy summary
                </button>
              </div>
            </div>
          </div>

          <ComparisonSummaryCard
            matches={sortedComparisonMatches}
            backendSummary={comparison?.summary}
          />

          <ComparisonControls
            matches={sortedComparisonMatches}
            visibleLabels={visibleLabels}
            onToggleLabel={handleToggleLabel}
            onResetFilters={handleResetFilters}
          />

          <SortingControl
            options={sortingOptions}
            selectedSort={selectedSort}
            onSelectSort={handleSelectSort}
          />

          <div className="mobile-article-tabs" aria-label="Article view">
            {['A', 'B'].map((side) => (
              <button
                className={
                  activeMobileArticle === side
                    ? 'mobile-article-tab active'
                    : 'mobile-article-tab'
                }
                type="button"
                key={side}
                onClick={() => setActiveMobileArticle(side)}
              >
                Article {side}
              </button>
            ))}
          </div>

          {!selectedMatch && sortedComparisonMatches.length > 0 && (
            <p className="match-selection-hint">
              Tip: click any highlighted paragraph pair to open its evidence panel.
            </p>
          )}

          <div
            className={
              selectedMatch
                ? 'results-layout results-layout--with-panel'
                : 'results-layout'
            }
          >
            <div className="article-grid">
              <div
                className={
                  activeMobileArticle === 'A'
                    ? 'article-grid__item'
                    : 'article-grid__item article-grid__item--inactive-mobile'
                }
              >
                <ArticlePanel
                  article={articleA}
                  error={getErrorForArticle(apiErrors, 'A')}
                  label="Article A"
                  side="A"
                  matches={sortedComparisonMatches}
                  visibleLabels={visibleLabels}
                  selectedMatchId={selectedMatchId}
                  onSelectMatch={handleSelectMatch}
                />
              </div>
              <div
                className={
                  activeMobileArticle === 'B'
                    ? 'article-grid__item'
                    : 'article-grid__item article-grid__item--inactive-mobile'
                }
              >
                <ArticlePanel
                  article={articleB}
                  error={getErrorForArticle(apiErrors, 'B')}
                  label="Article B"
                  side="B"
                  matches={sortedComparisonMatches}
                  visibleLabels={visibleLabels}
                  selectedMatchId={selectedMatchId}
                  onSelectMatch={handleSelectMatch}
                />
              </div>
            </div>

            <div className="sticky-explanation-slot">
              <MatchExplanationPanel
                selectedMatch={selectedMatch}
                matches={sortedComparisonMatches}
                articleA={articleA}
                articleB={articleB}
                scoreGuides={comparison?.score_guides}
                onSelectMatch={handleSelectMatch}
                onClose={() => handleSelectMatch(null)}
              />
            </div>
          </div>
        </section>
      </main>

      <footer>
        <p>T17B BREAD / News narrative comparison</p>
        <p>Highlighted evidence with explanations and filters.</p>
      </footer>

      {showBackToTop && (
        <button
          className="back-to-top-button"
          type="button"
          onClick={scrollToTop}
          aria-label="Back to top"
          title="Back to top"
        >
          <span aria-hidden="true">&uarr;</span>
        </button>
      )}
    </div>
  )
}

export default App


