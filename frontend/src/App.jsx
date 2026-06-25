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
    A: 'https://www.reuters.com/world/asia-pacific/us-waives-iran-sanctions-trump-says-he-will-do-what-i-have-to-if-tehran-2026-06-23/',
    B: 'https://apnews.com/article/4bbde727c7095c4ad9da0285ca79f1e1',
  },
  articles: [
    {
      article_ref: 'A',
      title:
        'U.S. waives Iran sanctions as Trump warns he will act if needed',
      source_domain: 'reuters.com',
      url: 'https://www.reuters.com/world/asia-pacific/us-waives-iran-sanctions-trump-says-he-will-do-what-i-have-to-if-tehran-2026-06-23/',
      paragraphs: [
        'The United States temporarily eased some restrictions affecting Iranian oil as negotiations between Washington and Tehran continued.',
        'President Donald Trump presented the measure as part of a diplomatic opening, while maintaining that the United States could take further action if Iran did not meet its commitments.',
        'The decision could allow Iran to increase oil sales during the waiver period and formed part of a wider package being discussed by negotiators.',
        'Officials remained cautious about whether the talks would produce a lasting agreement, with several security and nuclear issues still unresolved.',
      ],
    },
    {
      article_ref: 'B',
      title:
        "U.S. and Iran wrap high-level talks after 'encouraging progress'",
      source_domain: 'apnews.com',
      url: 'https://apnews.com/article/4bbde727c7095c4ad9da0285ca79f1e1',
      paragraphs: [
        'Senior officials from the United States and Iran concluded talks in Switzerland after reporting progress toward a broader agreement.',
        'The discussions covered nuclear oversight, regional security and arrangements concerning shipping through the Strait of Hormuz.',
        'A temporary waiver of some oil sanctions was among the incentives connected to the negotiations, alongside further technical discussions.',
        'Both sides described the meetings as constructive, although significant details would still need to be settled before a permanent deal.',
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

function ArticlePanel({ article, label, side }) {
  if (article) {
    return (
      <article className="article-panel article-panel--loaded">
        <div className="article-panel__heading">
          <span className={`article-badge article-badge--${side}`}>{side}</span>
          <div>
            <p className="eyebrow">
              {label} · {article.source_domain}
            </p>
            <h2>{article.title}</h2>
          </div>
        </div>

        <a
          className="article-source-link"
          href={article.url}
          target="_blank"
          rel="noreferrer"
        >
          View original article <span aria-hidden="true">↗</span>
        </a>

        <div className="article-copy">
          {article.paragraphs.map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
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
  const [errors, setErrors] = useState({})
  const [statusMessage, setStatusMessage] = useState('')
  const [articles, setArticles] = useState([])
  const [usingDemoCopy, setUsingDemoCopy] = useState(false)

  function loadDemoArticles() {
    setArticleAUrl(demoArticles.urls.A)
    setArticleBUrl(demoArticles.urls.B)
    setFocus('general')
    setErrors({})
    setArticles([])
    setUsingDemoCopy(true)
    setStatusMessage(
      'Demo URLs loaded. Select a focus and click Compare articles.',
    )
  }

  function handleSubmit(event) {
    event.preventDefault()

    const nextErrors = {}
    if (!isValidHttpUrl(articleAUrl)) {
      nextErrors.articleA = 'Enter a valid URL beginning with http:// or https://'
    }
    if (!isValidHttpUrl(articleBUrl)) {
      nextErrors.articleB = 'Enter a valid URL beginning with http:// or https://'
    }

    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0) {
      setArticles([])
      setStatusMessage('')
      return
    }

    const isDemoPair =
      articleAUrl.trim() === demoArticles.urls.A &&
      articleBUrl.trim() === demoArticles.urls.B

    if (isDemoPair) {
      const selectedFocus = focusOptions.find(
        (option) => option.value === focus,
      )
      setArticles(demoArticles.articles)
      setUsingDemoCopy(true)
      setStatusMessage(
        `Demo comparison loaded with the “${selectedFocus.label}” focus.`,
      )
    } else {
      setArticles([])
      setUsingDemoCopy(false)
      setStatusMessage(
        'Both URLs are valid. Live backend connection is the next step.',
      )
    }
  }

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
            Add two articles about the same event. We will prepare them for a
            clear, side-by-side narrative comparison.
          </p>

          <div className="demo-prompt">
            <div>
              <strong>Need a reliable demo?</strong>
              <span>Use our prepared Reuters and AP example.</span>
            </div>
            <button
              className="demo-button"
              type="button"
              onClick={loadDemoArticles}
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
                  onChange={(event) => setArticleAUrl(event.target.value)}
                  placeholder="https://news-outlet.com/article"
                  aria-describedby={
                    errors.articleA ? 'article-a-error' : undefined
                  }
                  aria-invalid={Boolean(errors.articleA)}
                />
                {errors.articleA && (
                  <p className="field-error" id="article-a-error">
                    {errors.articleA}
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
                  onChange={(event) => setArticleBUrl(event.target.value)}
                  placeholder="https://another-outlet.com/article"
                  aria-describedby={
                    errors.articleB ? 'article-b-error' : undefined
                  }
                  aria-invalid={Boolean(errors.articleB)}
                />
                {errors.articleB && (
                  <p className="field-error" id="article-b-error">
                    {errors.articleB}
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
                >
                  {focusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <button className="compare-button" type="submit">
                Compare articles
                <span aria-hidden="true">→</span>
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
            <p>Clean article text will appear below after comparison.</p>
          </div>

          <div className="article-grid">
            <ArticlePanel
              article={articles.find(
                (article) => article.article_ref === 'A',
              )}
              label="Left article"
              side="A"
            />
            <ArticlePanel
              article={articles.find(
                (article) => article.article_ref === 'B',
              )}
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
        <p>T17B BREAD · News narrative comparison</p>
        <p>Semantic highlighting arrives in Sprint 2.</p>
      </footer>
    </div>
  )
}

export default App
