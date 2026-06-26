import { useState } from 'react'
import './App.css'

const focusOptions = [
  { value: 'general', label: 'General comparison' },
  { value: 'political', label: 'Political framing' },
  { value: 'sentiment', label: 'Sentiment' },
  { value: 'economic', label: 'Economic focus' },
  { value: 'social', label: 'Social impact' },
]

const demoArticles = {
  urls: {
    A: 'https://www.aljazeera.com/news/2024/11/28/australia-passes-legislation-banning-under-16s-from-social-media',
    B: 'https://www.abc.net.au/news/2024-11-29/meta-snapchat-tiktok-respond-to-australian-social-media-ban/104664478',
  },
  articles: [
    {
      article_ref: 'A',
      title: 'Australia passes legislation banning under-16s from social media',
      source_domain: 'aljazeera.com',
      url: 'https://www.aljazeera.com/news/2024/11/28/australia-passes-legislation-banning-under-16s-from-social-media',
      paragraphs: [
        'Australia passed legislation banning children aged under 16 from using social media, creating one of the world’s strictest rules for online platforms.',
        'The law requires companies such as Instagram, Facebook and TikTok to prevent under-16s from holding accounts or face large financial penalties.',
        'Prime Minister Anthony Albanese argued that the measure would help protect young people from peer pressure, anxiety, scammers and online predators.',
        'Critics warned that the ban could limit support networks for vulnerable teenagers and raise privacy concerns around age verification.',
      ],
    },
    {
      article_ref: 'B',
      title:
        "Tech companies respond to Australia's social media ban for under-16s",
      source_domain: 'abc.net.au',
      url: 'https://www.abc.net.au/news/2024-11-29/meta-snapchat-tiktok-respond-to-australian-social-media-ban/104664478',
      paragraphs: [
        'Major technology companies responded with concern after Australia approved new laws banning children and young teenagers from social media.',
        'Meta, Snapchat and TikTok said they were disappointed by the legislation and raised questions about how the rules would be implemented.',
        'The companies said they supported online safety but argued that the government needed clearer guidance on age assurance and enforcement.',
        'The law will not take effect immediately, giving platforms and regulators time to work through technical compliance details.',
      ],
    },
  ],
}

function isValidHttpUrl(value) {
  try {
    const url = new URL(value.trim())
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

function getFocusLabel(focusValue) {
  return (
    focusOptions.find((option) => option.value === focusValue)?.label ??
    'General comparison'
  )
}

function getErrorForArticle(apiErrors, side) {
  return apiErrors.find((error) => error.article_ref === side)
}

function clearFieldError(errors, fieldName) {
  if (!errors[fieldName]) {
    return errors
  }

  const nextErrors = { ...errors }
  delete nextErrors[fieldName]
  return nextErrors
}

function ArticlePanel({ article, error, label, side }) {
  if (article) {
    return (
      <article className="article-panel article-panel--loaded">
        <div className="article-panel__heading">
          <span className={`article-badge article-badge--${side}`}>{side}</span>
          <div>
            <p className="eyebrow">
              {label} / {article.source_domain ?? 'Unknown source'}
            </p>
            <h2>{article.title ?? 'Untitled article'}</h2>
          </div>
        </div>

        <a
          className="article-source-link"
          href={article.url}
          target="_blank"
          rel="noreferrer"
        >
          View original article <span aria-hidden="true">-&gt;</span>
        </a>

        <div className="article-copy">
          {article.paragraphs?.map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
        </div>
      </article>
    )
  }

  if (error) {
    return (
      <article className="article-panel article-panel--error">
        <div className="article-panel__heading">
          <span className={`article-badge article-badge--${side}`}>{side}</span>
          <div>
            <p className="eyebrow">{label}</p>
            <h2>Article could not be loaded</h2>
          </div>
        </div>

        <div className="article-error-box">
          <p>
            <strong>Stage:</strong> {error.stage}
          </p>
          <p>{error.message}</p>
        </div>
      </article>
    )
  }

  return (
    <article className="article-panel">
      <div className="article-panel__heading">
        <span className={`article-badge article-badge--${side}`}>{side}</span>
        <div>
          <p className="eyebrow">{label}</p>
          <h2>Waiting for an article</h2>
        </div>
      </div>

      <div className="article-placeholder" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </div>

      <p className="empty-message">
        Enter a URL above to load the cleaned article here.
      </p>
    </article>
  )
}

function App() {
  const [articleAUrl, setArticleAUrl] = useState('')
  const [articleBUrl, setArticleBUrl] = useState('')
  const [focus, setFocus] = useState('general')
  const [formErrors, setFormErrors] = useState({})
  const [apiErrors, setApiErrors] = useState([])
  const [statusMessage, setStatusMessage] = useState('')
  const [articles, setArticles] = useState([])
  const [usingDemoCopy, setUsingDemoCopy] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const canCompare =
    isValidHttpUrl(articleAUrl) && isValidHttpUrl(articleBUrl)

  function loadDemoArticles() {
    setArticleAUrl(demoArticles.urls.A)
    setArticleBUrl(demoArticles.urls.B)
    setFocus('general')
    setFormErrors({})
    setApiErrors([])
    setArticles([])
    setUsingDemoCopy(false)
    setStatusMessage(
      'Demo URLs loaded. Click Compare articles to try the live backend.',
    )
  }

  function showOfflineDemoFallback(message) {
    setArticles(demoArticles.articles)
    setApiErrors([])
    setUsingDemoCopy(true)
    setStatusMessage(message)
  }

  function handleArticleAUrlChange(event) {
    setArticleAUrl(event.target.value)
    setFormErrors((currentErrors) =>
      clearFieldError(currentErrors, 'articleA'),
    )
  }

  function handleArticleBUrlChange(event) {
    setArticleBUrl(event.target.value)
    setFormErrors((currentErrors) =>
      clearFieldError(currentErrors, 'articleB'),
    )
  }

  async function handleSubmit(event) {
    event.preventDefault()

    const nextFormErrors = {}
    if (!isValidHttpUrl(articleAUrl)) {
      nextFormErrors.articleA =
        'Enter a valid URL beginning with http:// or https://'
    }
    if (!isValidHttpUrl(articleBUrl)) {
      nextFormErrors.articleB =
        'Enter a valid URL beginning with http:// or https://'
    }

    setFormErrors(nextFormErrors)

    if (Object.keys(nextFormErrors).length > 0) {
      setArticles([])
      setApiErrors([])
      setUsingDemoCopy(false)
      setStatusMessage('')
      return
    }

    const isDemoPair =
      articleAUrl.trim() === demoArticles.urls.A &&
      articleBUrl.trim() === demoArticles.urls.B

    setIsLoading(true)
    setArticles([])
    setApiErrors([])
    setUsingDemoCopy(false)
    setStatusMessage('Sending URLs to the backend...')

    try {
      const response = await fetch('/api/compare', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          article_a_url: articleAUrl.trim(),
          article_b_url: articleBUrl.trim(),
          focus,
        }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          data?.detail?.message ?? `Backend returned HTTP ${response.status}`,
        )
      }

      const returnedArticles = data.articles ?? []
      const returnedErrors = data.errors ?? []

      setArticles(returnedArticles)
      setApiErrors(returnedErrors)

      if (returnedArticles.length > 0 && returnedErrors.length === 0) {
        setStatusMessage(
          `Live backend result loaded with the "${getFocusLabel(data.focus)}" focus.`,
        )
      } else if (returnedArticles.length > 0) {
        setStatusMessage(
          'Partial backend result loaded. One article could not be processed.',
        )
      } else {
        setStatusMessage('The backend could not process either article.')
      }
    } catch (error) {
      if (isDemoPair) {
        showOfflineDemoFallback(
          'Live backend was unavailable, so the offline demo copy was loaded.',
        )
      } else {
        setArticles([])
        setApiErrors([])
        setUsingDemoCopy(false)
        setStatusMessage(
          `Could not reach the backend. Start the backend and try again. ${error.message}`,
        )
      }
    } finally {
      setIsLoading(false)
    }
  }

  const articleA = articles.find((article) => article.article_ref === 'A')
  const articleB = articles.find((article) => article.article_ref === 'B')

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="Narrative Diff home">
          <span className="brand-mark" aria-hidden="true">
            ND
          </span>
          <span>Narrative Diff</span>
        </a>
        <span className="sprint-label">Sprint 1 prototype</span>
      </header>

      <main>
        <section className="hero-section">
          <p className="eyebrow">Compare reporting. See the difference.</p>
          <h1>How does the story change between news outlets?</h1>
          <p className="hero-copy">
            Add two articles about the same event. The frontend sends them to
            the backend, then displays cleaned article text side by side.
          </p>

          <div className="demo-prompt">
            <div>
              <strong>Need a reliable demo?</strong>
              <span>
                Load the Al Jazeera and ABC example. If the backend is unavailable,
                the page falls back to offline demo copy.
              </span>
            </div>
            <button
              className="demo-button"
              type="button"
              onClick={loadDemoArticles}
              disabled={isLoading}
            >
              Load demo articles
            </button>
          </div>

          <form className="compare-form" onSubmit={handleSubmit} noValidate>
            <div className="url-fields">
              <div className="field-group">
                <label htmlFor="article-a-url">
                  <span className="field-number">A</span>
                  First article URL
                </label>
                <input
                  id="article-a-url"
                  type="url"
                  value={articleAUrl}
                  onChange={handleArticleAUrlChange}
                  placeholder="https://news-outlet.com/article"
                  aria-describedby={
                    formErrors.articleA ? 'article-a-error' : undefined
                  }
                  aria-invalid={Boolean(formErrors.articleA)}
                  disabled={isLoading}
                />
                {formErrors.articleA && (
                  <p className="field-error" id="article-a-error">
                    {formErrors.articleA}
                  </p>
                )}
              </div>

              <div className="field-group">
                <label htmlFor="article-b-url">
                  <span className="field-number field-number--b">B</span>
                  Second article URL
                </label>
                <input
                  id="article-b-url"
                  type="url"
                  value={articleBUrl}
                  onChange={handleArticleBUrlChange}
                  placeholder="https://another-outlet.com/article"
                  aria-describedby={
                    formErrors.articleB ? 'article-b-error' : undefined
                  }
                  aria-invalid={Boolean(formErrors.articleB)}
                  disabled={isLoading}
                />
                {formErrors.articleB && (
                  <p className="field-error" id="article-b-error">
                    {formErrors.articleB}
                  </p>
                )}
              </div>
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

            {statusMessage && (
              <p
                className={`status-message${articles.length ? ' status-message--success' : ''}`}
                role="status"
              >
                {statusMessage}
              </p>
            )}
          </form>
        </section>

        <section className="results-section" aria-labelledby="results-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Article viewer</p>
              <h2 id="results-title">Side-by-side reading</h2>
            </div>
            <p>Clean article text appears below after comparison.</p>
          </div>

          <div className="article-grid">
            <ArticlePanel
              article={articleA}
              error={getErrorForArticle(apiErrors, 'A')}
              label="Left article"
              side="A"
            />
            <ArticlePanel
              article={articleB}
              error={getErrorForArticle(apiErrors, 'B')}
              label="Right article"
              side="B"
            />
          </div>

          {articles.length > 0 && usingDemoCopy && (
            <p className="demo-disclaimer">
              Demo copy is a short paraphrased sample prepared for offline
              presentation. The links above open the original reporting.
            </p>
          )}
        </section>
      </main>

      <footer>
        <p>T17B BREAD / News narrative comparison</p>
        <p>Semantic highlighting arrives in Sprint 2.</p>
      </footer>
    </div>
  )
}

export default App
