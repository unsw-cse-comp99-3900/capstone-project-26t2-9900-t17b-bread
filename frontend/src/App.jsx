import { useEffect, useRef, useState } from 'react'
import {
  maxUploadSizeBytes,
  minTextChars,
} from './config/appConfig'
import { AuthModal, HistoryPanel, SaveOptionsModal } from './components/AccountPanels'
import { AppHeader } from './components/AppHeader'
import { ArticlePanel } from './components/ArticlePanel'
import {
  ComparisonControls,
  RelevanceNoticeModal,
  ComparisonSummaryCard,
  SortingControl,
} from './components/ComparisonResults'
import { CompareInputSection } from './components/CompareInputSection'
import { MatchExplanationPanel } from './components/MatchExplanationPanel'
import { useArticleInputs } from './hooks/useArticleInputs'
import { useAuth } from './hooks/useAuth'
import { useBackendStatus } from './hooks/useBackendStatus'
import { useComparison } from './hooks/useComparison'
import { useDemoSamples } from './hooks/useDemoSamples'
import { useResultActions } from './hooks/useResultActions'
import { groupDemoSamples } from './utils/demo'
import { getErrorForArticle } from './utils/comparison'
import './styles/index.css'

function App() {
  const [formErrors, setFormErrors] = useState({})
  const [statusMessage, setStatusMessage] = useState('')
  const [historyItems, setHistoryItems] = useState([])
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [isSaveOptionsOpen, setIsSaveOptionsOpen] = useState(false)
  const [isAboutOpen, setIsAboutOpen] = useState(false)
  const [isRelevanceNoticeOpen, setIsRelevanceNoticeOpen] = useState(false)
  const [isTimeoutNoticeOpen, setIsTimeoutNoticeOpen] = useState(false)
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
    pendingVerificationEmail,
    developmentVerificationCode,
    setDevelopmentVerificationCode,
    resendSecondsRemaining,
    authError,
    setAuthError,
    isAuthSubmitting,
    refreshAccountHistory,
    handleAuthSubmit,
    handleLogout,
    handleResendCode,
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
    relevanceNotice,
    resetComparisonWorkspace,
    selectedMatch,
    selectedMatchId,
    selectedSort,
    setActiveMobileArticle,
    setFocus,
    sortedComparisonMatches,
    sortingOptions,
    timeoutNotice,
    setTimeoutNotice,
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

  useEffect(() => {
    if (relevanceNotice) {
      setIsRelevanceNoticeOpen(true)
    }
  }, [relevanceNotice])

  useEffect(() => {
    if (timeoutNotice) {
      setIsTimeoutNoticeOpen(true)
    }
  }, [timeoutNotice])

  const demoGroups = groupDemoSamples(demoSamples)
  const {
    handleClearHistory,
    handleCopySummary,
    handleDeleteHistoryItem,
    handleDownloadHtmlReport,
    handleOpenSaveOptions,
  } = useResultActions({
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
  })

  function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function scrollToResults() {
    resultsSectionRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
  }

  return (
    <div className="app-shell">
      <AppHeader
        backendStatus={backendStatus}
        currentUser={currentUser}
        historyCount={historyItems.length}
        isAboutOpen={isAboutOpen}
        onAboutClose={() => setIsAboutOpen(false)}
        onAboutOpen={() => setIsAboutOpen(true)}
        onHistoryToggle={() => setIsHistoryOpen((isOpen) => !isOpen)}
        onLoginOpen={() => {
          setAuthMode('login')
          setAuthError('')
          setIsAuthOpen(true)
        }}
        onLogout={handleLogout}
      />

      <AuthModal
        isOpen={isAuthOpen}
        mode={authMode}
        authForm={authForm}
        pendingVerificationEmail={pendingVerificationEmail}
        developmentVerificationCode={developmentVerificationCode}
        resendSecondsRemaining={resendSecondsRemaining}
        error={authError}
        isSubmitting={isAuthSubmitting}
        onClose={() => setIsAuthOpen(false)}
        onModeChange={(nextMode) => {
          setAuthMode(nextMode)
          setAuthError('')
          setDevelopmentVerificationCode('')
        }}
        onFormChange={setAuthForm}
        onSubmit={handleAuthSubmit}
        onResendCode={handleResendCode}
      />

      <SaveOptionsModal
        isOpen={isSaveOptionsOpen}
        currentUser={currentUser}
        onClose={() => setIsSaveOptionsOpen(false)}
        onDownloadHtml={handleDownloadHtmlReport}
      />

      <RelevanceNoticeModal
        notice={relevanceNotice}
        isOpen={isRelevanceNoticeOpen}
        onClose={() => setIsRelevanceNoticeOpen(false)}
      />

      <RelevanceNoticeModal
        notice={timeoutNotice}
        isOpen={isTimeoutNoticeOpen}
        onClose={() => {
          setIsTimeoutNoticeOpen(false)
          setTimeoutNotice(null)
        }}
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

        <CompareInputSection
          articleInputA={articleInputA}
          articleInputB={articleInputB}
          canCompare={canCompare}
          demoGroups={demoGroups}
          demoLoadError={demoLoadError}
          demoSamples={demoSamples}
          focus={focus}
          formErrors={formErrors}
          hasLoadedArticles={articles.length > 0}
          isLoading={isLoading}
          onArticleAClear={clearArticleAInput}
          onArticleAConvertWord={convertArticleAToWord}
          onArticleAFileChange={handleArticleAFileChange}
          onArticleAModeChange={handleArticleAModeChange}
          onArticleATextChange={handleArticleATextChange}
          onArticleAUrlChange={handleArticleAUrlChange}
          onArticleBClear={clearArticleBInput}
          onArticleBConvertWord={convertArticleBToWord}
          onArticleBFileChange={handleArticleBFileChange}
          onArticleBModeChange={handleArticleBModeChange}
          onArticleBTextChange={handleArticleBTextChange}
          onArticleBUrlChange={handleArticleBUrlChange}
          onDemoLoad={loadDemoSample}
          onFocusChange={setFocus}
          onSubmit={handleSubmit}
          progress={progress}
          readinessMessage={readinessMessage}
          statusMessage={statusMessage}
        />

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
              {sortedComparisonMatches.length > 0 && (
                <div className="section-button-row">
                  <button
                    className="save-results-button"
                    type="button"
                    onClick={handleCopySummary}
                  >
                    Copy summary
                  </button>
                </div>
              )}
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


