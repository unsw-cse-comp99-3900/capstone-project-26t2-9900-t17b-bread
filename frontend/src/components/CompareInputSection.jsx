import { focusOptions } from '../config/appConfig'
import { ArticleSourceField } from './ArticleInputs'

export function CompareInputSection({
  articleInputA,
  articleInputB,
  canCompare,
  demoGroups,
  demoLoadError,
  demoSamples,
  focus,
  formErrors,
  hasLoadedArticles,
  isLoading,
  onArticleAFileChange,
  onArticleAModeChange,
  onArticleATextChange,
  onArticleAUrlChange,
  onArticleBFileChange,
  onArticleBModeChange,
  onArticleBTextChange,
  onArticleBUrlChange,
  onArticleAClear,
  onArticleBClear,
  onArticleAConvertWord,
  onArticleBConvertWord,
  onDemoLoad,
  onFocusChange,
  onSubmit,
  progress,
  readinessMessage,
  statusMessage,
}) {
  return (
    <section className="hero-section">
      <p className="eyebrow">Compare reporting. See the difference.</p>
      <h1>How does the story change between news outlets?</h1>
      <p className="hero-copy">
        Compare two reports on the same story and see where they align, diverge,
        or leave details out.
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
                          onDemoLoad(selectedSample)
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

      <form className="compare-form" onSubmit={onSubmit} noValidate>
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
            onModeChange={onArticleAModeChange}
            onUrlChange={onArticleAUrlChange}
            onTextChange={onArticleATextChange}
            onFileChange={onArticleAFileChange}
            onConvertWord={onArticleAConvertWord}
            onClear={onArticleAClear}
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
            onModeChange={onArticleBModeChange}
            onUrlChange={onArticleBUrlChange}
            onTextChange={onArticleBTextChange}
            onFileChange={onArticleBFileChange}
            onConvertWord={onArticleBConvertWord}
            onClear={onArticleBClear}
          />
        </div>

        <div className="form-actions">
          <div className="focus-field">
            <label htmlFor="comparison-focus">Comparison focus</label>
            <select
              id="comparison-focus"
              value={focus}
              onChange={(event) => onFocusChange(event.target.value)}
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
            className={`status-message${hasLoadedArticles ? ' status-message--success' : ''}`}
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
  )
}
