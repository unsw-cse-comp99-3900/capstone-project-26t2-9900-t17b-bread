import { useState } from 'react'
import './App.css'

const focusOptions = [
  { value: 'general', label: 'General comparison' },
  { value: 'political', label: 'Political framing' },
  { value: 'sentiment', label: 'Sentiment' },
  { value: 'economic', label: 'Economic focus' },
  { value: 'social', label: 'Social impact' },
]

const relationshipOptions = [
  { value: 'aligned', label: 'Aligned' },
  { value: 'partially_aligned', label: 'Partially aligned' },
  { value: 'divergent', label: 'Divergent' },
]

const articleInputModes = [
  { value: 'url', label: 'URL' },
  { value: 'upload', label: 'PDF / Word' },
]

const maxUploadSizeBytes = 10 * 1024 * 1024

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
      sentences: [
        {
          id: 'A-0',
          article_ref: 'A',
          text: 'Australia passed legislation banning children aged under 16 from using social media, creating one of the world鈥檚 strictest rules for online platforms.',
          paragraph_index: 0,
          sentence_index: 0,
          char_start: 0,
          char_end: 132,
        },
        {
          id: 'A-1',
          article_ref: 'A',
          text: 'The law requires companies such as Instagram, Facebook and TikTok to prevent under-16s from holding accounts or face large financial penalties.',
          paragraph_index: 1,
          sentence_index: 1,
          char_start: 133,
          char_end: 269,
        },
        {
          id: 'A-2',
          article_ref: 'A',
          text: 'Prime Minister Anthony Albanese argued that the measure would help protect young people from peer pressure, anxiety, scammers and online predators.',
          paragraph_index: 2,
          sentence_index: 2,
          char_start: 270,
          char_end: 410,
        },
        {
          id: 'A-3',
          article_ref: 'A',
          text: 'Critics warned that the ban could limit support networks for vulnerable teenagers and raise privacy concerns around age verification.',
          paragraph_index: 3,
          sentence_index: 3,
          char_start: 411,
          char_end: 531,
        },
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
      sentences: [
        {
          id: 'B-0',
          article_ref: 'B',
          text: 'Major technology companies responded with concern after Australia approved new laws banning children and young teenagers from social media.',
          paragraph_index: 0,
          sentence_index: 0,
          char_start: 0,
          char_end: 128,
        },
        {
          id: 'B-1',
          article_ref: 'B',
          text: 'Meta, Snapchat and TikTok said they were disappointed by the legislation and raised questions about how the rules would be implemented.',
          paragraph_index: 1,
          sentence_index: 1,
          char_start: 129,
          char_end: 257,
        },
        {
          id: 'B-2',
          article_ref: 'B',
          text: 'The companies said they supported online safety but argued that the government needed clearer guidance on age assurance and enforcement.',
          paragraph_index: 2,
          sentence_index: 2,
          char_start: 258,
          char_end: 383,
        },
        {
          id: 'B-3',
          article_ref: 'B',
          text: 'The law will not take effect immediately, giving platforms and regulators time to work through technical compliance details.',
          paragraph_index: 3,
          sentence_index: 3,
          char_start: 384,
          char_end: 495,
        },
      ],
    },
  ],
  comparison: {
    matches: [
      {
        sentence_a_id: 'A-0',
        sentence_b_id: 'B-0',
        label: 'aligned',
        score: 0.91,
        explanation:
          'Both sections describe the same core event: Australia approving a social media ban for young users.',
      },
      {
        sentence_a_id: 'A-1',
        sentence_b_id: 'B-1',
        label: 'partially_aligned',
        score: 0.73,
        explanation:
          'Both sections discuss platform obligations, but article A emphasises penalties while article B emphasises company concerns about implementation.',
      },
      {
        sentence_a_id: 'A-2',
        sentence_b_id: 'B-2',
        label: 'divergent',
        score: 0.48,
        explanation:
          'Article A frames the measure through government protection claims, while article B foregrounds technology companies asking for clearer rules.',
      },
    ],
  },
}

const friendlyErrorMessages = {
  url_missing: {
    title: 'Missing article link',
    message: 'Please paste a complete article URL before comparing.',
    action: 'Use a link that starts with http:// or https://.',
  },
  url_invalid_scheme: {
    title: 'Link format is not supported',
    message: 'The article link needs to be a normal web link.',
    action: 'Check that it starts with http:// or https://.',
  },
  url_missing_host: {
    title: 'Incomplete article link',
    message: 'This link is missing the website name.',
    action: 'Paste the full article URL from your browser address bar.',
  },
  fetch_timeout: {
    title: 'The website took too long to respond',
    message: 'The article site may be slow or temporarily unavailable.',
    action: 'Try again later, or use a different article link.',
  },
  fetch_connection_failed: {
    title: 'Could not connect to the website',
    message: 'The link may be wrong, blocked, or unavailable from this server.',
    action: 'Open the link in your browser to check it, then try again.',
  },
  fetch_http_401: {
    title: 'This article requires sign-in',
    message: 'The news site did not allow access without an account.',
    action: 'Use a public article link, or upload a saved PDF/Word copy when file upload is available.',
  },
  fetch_http_403: {
    title: 'The website blocked access',
    message: 'Some news sites block automated article fetching.',
    action: 'Try another source, or upload a saved PDF/Word copy when file upload is available.',
  },
  fetch_http_404: {
    title: 'Article page was not found',
    message: 'The URL may be old, mistyped, or no longer available.',
    action: 'Check the link and paste the article URL again.',
  },
  fetch_http_error: {
    title: 'The website returned an error',
    message: 'The article page could not be downloaded from the news site.',
    action: 'Try again later or use another article link.',
  },
  fetch_page_too_large: {
    title: 'The page is too large to process',
    message: 'This link may point to a feed, homepage, or very large page instead of one article.',
    action: 'Use the direct URL for a single news article.',
  },
  extraction_paywall: {
    title: 'This article may be behind a paywall',
    message: 'The news site appears to require a subscription or membership to read the full article.',
    action: 'Use a publicly accessible article, or upload a saved PDF/Word copy when file upload is available.',
  },
  extraction_login_required: {
    title: 'This article requires login',
    message: 'The article text is not visible until a reader signs in.',
    action: 'Sign in on the news site and save the article as PDF/Word, or use another public link.',
  },
  extraction_not_news_page: {
    title: 'This does not look like a news article',
    message: 'The page may be a homepage, live feed, topic page, or search result.',
    action: 'Paste the URL for a specific article page.',
  },
  extraction_js_rendered: {
    title: 'The article text could not be read',
    message: 'This site loads the story in a way the backend cannot extract automatically.',
    action: 'Try another source, or upload a saved PDF/Word copy when file upload is available.',
  },
  extraction_empty: {
    title: 'No readable article text found',
    message: 'The backend reached the page, but could not find enough article content.',
    action: 'Check that the link opens a full article, not a video page or listing page.',
  },
  upload_unsupported_type: {
    title: 'File type is not supported',
    message: 'Only PDF and Word documents can be processed.',
    action: 'Upload a .pdf or .docx file.',
  },
  upload_file_too_large: {
    title: 'File is too large',
    message: 'The uploaded document is bigger than the current limit.',
    action: 'Use a file under 10MB.',
  },
  upload_parse_failed: {
    title: 'File could not be read',
    message: 'The document may be corrupted, password-protected, or not text-based.',
    action: 'Try exporting the article again as PDF or Word.',
  },
  upload_empty_document: {
    title: 'No readable text found in the file',
    message: 'The uploaded document does not contain enough extractable article text.',
    action: 'Check the file contents and upload a readable copy.',
  },
}

function isValidHttpUrl(value) {
  try {
    const url = new URL(value.trim())
    return url.protocol === 'http:' || url.protocol === 'https:'
  } catch {
    return false
  }
}

function isAllowedUpload(file) {
  if (!file) {
    return false
  }

  const fileName = file.name.toLowerCase()
  return fileName.endsWith('.pdf') || fileName.endsWith('.docx')
}

function isValidUpload(file) {
  return Boolean(file) && isAllowedUpload(file) && file.size <= maxUploadSizeBytes
}

function getUrlHost(value) {
  try {
    return new URL(value.trim()).hostname.replace(/^www\./, '')
  } catch {
    return ''
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

function getInitialFilters() {
  return relationshipOptions.reduce(
    (filters, option) => ({ ...filters, [option.value]: true }),
    {},
  )
}

function getFriendlyError(error) {
  return (
    friendlyErrorMessages[error?.code] ?? {
      title: 'Article could not be loaded',
      message:
        error?.message ??
        'Something went wrong while trying to process this article.',
      action: 'Check the link and try again, or use another source.',
    }
  )
}

function normalizeLabel(label) {
  if (label === 'partial') {
    return 'partially_aligned'
  }
  return relationshipOptions.some((option) => option.value === label)
    ? label
    : 'partially_aligned'
}

function normalizeMatch(match, index) {
  const label = normalizeLabel(match.label ?? match.relationship)
  const sentenceAId =
    match.sentence_a_id ??
    match.article_a_sentence_id ??
    match.a_sentence_id ??
    match.left_sentence_id
  const sentenceBId =
    match.sentence_b_id ??
    match.article_b_sentence_id ??
    match.b_sentence_id ??
    match.right_sentence_id

  return {
    ...match,
    id: match.id ?? `${sentenceAId ?? 'A'}-${sentenceBId ?? 'B'}-${index}`,
    label,
    sentenceAId,
    sentenceBId,
    explanation:
      match.explanation ??
      'This match was returned by the comparison pipeline.',
  }
}

function getComparisonMatches(comparison) {
  return (comparison?.matches ?? comparison?.alignments ?? []).map(
    normalizeMatch,
  )
}

function getMatchForSentence(matches, side, sentenceId) {
  return matches.find((match) =>
    side === 'A'
      ? match.sentenceAId === sentenceId
      : match.sentenceBId === sentenceId,
  )
}

function getSentenceText(article, sentenceId) {
  return article?.sentences?.find((sentence) => sentence.id === sentenceId)?.text
}

function getCompareReadinessMessage(canCompare, isLoading) {
  if (isLoading || canCompare) {
    return ''
  }

  return 'Add two valid article sources to compare.'
}

function parseApiError(errorPayload) {
  if (typeof errorPayload?.detail === 'string') {
    return errorPayload.detail
  }

  return (
    errorPayload?.detail?.message ??
    errorPayload?.error?.message ??
    'The backend could not complete the comparison.'
  )
}

async function parseEventStream(response, onProgress) {
  const reader = response.body?.getReader()
  if (!reader) {
    return response.json()
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split('\n\n')
    buffer = chunks.pop() ?? ''

    for (const chunk of chunks) {
      const lines = chunk.split('\n')
      const eventLine = lines.find((line) => line.startsWith('event:'))
      const dataLine = lines.find((line) => line.startsWith('data:'))

      if (!eventLine || !dataLine) {
        continue
      }

      const event = eventLine.replace('event:', '').trim()
      const data = JSON.parse(dataLine.replace('data:', '').trim())

      if (event === 'progress') {
        onProgress(data)
      }

      if (event === 'result') {
        return data
      }
    }
  }

  throw new Error('The backend stream ended before returning a result.')
}

function clearFieldError(errors, fieldName) {
  if (!errors[fieldName]) {
    return errors
  }

  const nextErrors = { ...errors }
  delete nextErrors[fieldName]
  return nextErrors
}

function ArticleSourceField({
  side,
  title,
  mode,
  url,
  file,
  error,
  isLoading,
  onModeChange,
  onUrlChange,
  onFileChange,
}) {
  const inputId = `article-${side.toLowerCase()}-url`
  const fileId = `article-${side.toLowerCase()}-file`
  const errorId = `article-${side.toLowerCase()}-error`
  const urlHost = getUrlHost(url)

  return (
    <div className="field-group">
      <div className="field-header">
        <label htmlFor={mode === 'url' ? inputId : fileId}>
          <span className={`field-number${side === 'B' ? ' field-number--b' : ''}`}>
            {side}
          </span>
          {title}
        </label>

        <div className="source-toggle" aria-label={`${title} source type`}>
          {articleInputModes.map((option) => (
            <button
              className={
                mode === option.value
                  ? 'source-toggle__button active'
                  : 'source-toggle__button'
              }
              type="button"
              key={option.value}
              onClick={() => onModeChange(option.value)}
              disabled={isLoading}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {mode === 'url' ? (
        <>
          <input
            className="url-input"
            id={inputId}
            type="url"
            value={url}
            onChange={onUrlChange}
            placeholder="https://news-outlet.com/article"
            aria-describedby={error ? errorId : undefined}
            aria-invalid={Boolean(error)}
            disabled={isLoading}
          />
          {urlHost && <p className="input-hint">Source: {urlHost}</p>}
        </>
      ) : (
        <>
          <label
            className={`file-picker${file ? ' file-picker--selected' : ''}`}
            htmlFor={fileId}
          >
            <input
              id={fileId}
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={onFileChange}
              aria-describedby={error ? errorId : undefined}
              aria-invalid={Boolean(error)}
              disabled={isLoading}
            />
            <span>{file ? file.name : 'Choose a PDF or Word file'}</span>
          </label>
          <p className="input-hint">
            Use saved articles, paywalled pages, or subscription content.
          </p>
        </>
      )}

      {error && (
        <p className="field-error" id={errorId}>
          {error}
        </p>
      )}
    </div>
  )
}

function SentenceButton({
  sentence,
  match,
  isVisible,
  isSelected,
  onSelectMatch,
}) {
  if (!match) {
    return <span>{sentence.text} </span>
  }

  if (!isVisible) {
    return null
  }

  return (
    <button
      className={`comparison-sentence comparison-sentence--${match.label}${
        isSelected ? ' comparison-sentence--selected' : ''
      }`}
      type="button"
      onClick={() => onSelectMatch(match.id)}
    >
      {sentence.text}
    </button>
  )
}

function ArticlePanel({
  article,
  error,
  label,
  side,
  matches,
  visibleLabels,
  selectedMatchId,
  onSelectMatch,
}) {
  if (article) {
    const sentencesByParagraph = (article.sentences ?? []).reduce(
      (groups, sentence) => {
        const paragraphIndex = sentence.paragraph_index ?? 0
        return {
          ...groups,
          [paragraphIndex]: [...(groups[paragraphIndex] ?? []), sentence],
        }
      },
      {},
    )

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
          {article.paragraphs?.map((paragraph, paragraphIndex) => {
            const paragraphSentences = sentencesByParagraph[paragraphIndex] ?? []

            if (paragraphSentences.length === 0) {
              return <p key={paragraph}>{paragraph}</p>
            }

            return (
              <p key={paragraph}>
                {paragraphSentences.map((sentence) => {
                  const match = getMatchForSentence(matches, side, sentence.id)
                  return (
                    <SentenceButton
                      key={sentence.id}
                      sentence={sentence}
                      match={match}
                      isVisible={!match || visibleLabels[match.label]}
                      isSelected={match?.id === selectedMatchId}
                      onSelectMatch={onSelectMatch}
                    />
                  )
                })}
              </p>
            )
          })}
        </div>
      </article>
    )
  }

  if (error) {
    const friendlyError = getFriendlyError(error)

    return (
      <article className="article-panel article-panel--error">
        <div className="article-panel__heading">
          <span className={`article-badge article-badge--${side}`}>{side}</span>
          <div>
            <p className="eyebrow">{label}</p>
            <h2>{friendlyError.title}</h2>
          </div>
        </div>

        <div className="article-error-box">
          <p>{friendlyError.message}</p>
          <p className="article-error-action">{friendlyError.action}</p>
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
          <h2>Waiting for article</h2>
        </div>
      </div>

      <div className="article-placeholder" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </div>

      <p className="empty-message">
        Add a URL or upload a document to begin.
      </p>
    </article>
  )
}

function ComparisonControls({
  matches,
  visibleLabels,
  selectedMatch,
  articleA,
  articleB,
  onToggleLabel,
  onResetFilters,
}) {
  if (matches.length === 0) {
    return null
  }

  return (
    <section className="comparison-inspector" aria-labelledby="inspector-title">
      <div className="filter-panel">
        <div>
          <p className="eyebrow">Relationship filters</p>
          <h2 id="inspector-title">Comparison highlights</h2>
        </div>

        <div className="filter-controls" aria-label="Highlight filters">
          {relationshipOptions.map((option) => (
            <label
              className={`filter-toggle filter-toggle--${option.value}`}
              key={option.value}
            >
              <input
                type="checkbox"
                checked={visibleLabels[option.value]}
                onChange={() => onToggleLabel(option.value)}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>

        <button className="reset-filters-button" type="button" onClick={onResetFilters}>
          Reset filters
        </button>
      </div>

      <aside className="explanation-panel" aria-live="polite">
        {selectedMatch ? (
          <>
            <div className="explanation-panel__header">
              <span
                className={`relationship-pill relationship-pill--${selectedMatch.label}`}
              >
                {
                  relationshipOptions.find(
                    (option) => option.value === selectedMatch.label,
                  )?.label
                }
              </span>
              {typeof selectedMatch.score === 'number' && (
                <span className="match-score">
                  Score {Math.round(selectedMatch.score * 100)}%
                </span>
              )}
            </div>

            <p>{selectedMatch.explanation}</p>

            <div className="matched-text">
              <div>
                <strong>Article A</strong>
                <span>
                  {getSentenceText(articleA, selectedMatch.sentenceAId) ??
                    'Matched text unavailable.'}
                </span>
              </div>
              <div>
                <strong>Article B</strong>
                <span>
                  {getSentenceText(articleB, selectedMatch.sentenceBId) ??
                    'Matched text unavailable.'}
                </span>
              </div>
            </div>
          </>
        ) : (
          <p>
            Click any highlighted sentence to see the matching evidence and why
            it was labelled.
          </p>
        )}
      </aside>
    </section>
  )
}

function App() {
  const [articleAMode, setArticleAMode] = useState('url')
  const [articleBMode, setArticleBMode] = useState('url')
  const [articleAUrl, setArticleAUrl] = useState('')
  const [articleBUrl, setArticleBUrl] = useState('')
  const [articleAFile, setArticleAFile] = useState(null)
  const [articleBFile, setArticleBFile] = useState(null)
  const [focus, setFocus] = useState('general')
  const [formErrors, setFormErrors] = useState({})
  const [apiErrors, setApiErrors] = useState([])
  const [statusMessage, setStatusMessage] = useState('')
  const [progress, setProgress] = useState(null)
  const [articles, setArticles] = useState([])
  const [comparison, setComparison] = useState(null)
  const [visibleLabels, setVisibleLabels] = useState(getInitialFilters)
  const [selectedMatchId, setSelectedMatchId] = useState(null)
  const [activeMobileArticle, setActiveMobileArticle] = useState('A')
  const [usingDemoCopy, setUsingDemoCopy] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const canCompare =
    (articleAMode === 'url'
      ? isValidHttpUrl(articleAUrl)
      : isValidUpload(articleAFile)) &&
    (articleBMode === 'url'
      ? isValidHttpUrl(articleBUrl)
      : isValidUpload(articleBFile))

  function loadDemoArticles() {
    const demoMatches = getComparisonMatches(demoArticles.comparison)

    setArticleAMode('url')
    setArticleBMode('url')
    setArticleAUrl(demoArticles.urls.A)
    setArticleBUrl(demoArticles.urls.B)
    setArticleAFile(null)
    setArticleBFile(null)
    setFocus('general')
    setFormErrors({})
    setApiErrors([])
    setProgress(null)
    setArticles(demoArticles.articles)
    setComparison(demoArticles.comparison)
    setSelectedMatchId(demoMatches[0]?.id ?? null)
    setActiveMobileArticle('A')
    setUsingDemoCopy(true)
    setStatusMessage(
      'Demo articles loaded with Sprint 2 highlights. Click Compare articles to try the live backend.',
    )
  }

  function showOfflineDemoFallback(message) {
    const demoMatches = getComparisonMatches(demoArticles.comparison)

    setProgress(null)
    setArticles(demoArticles.articles)
    setComparison(demoArticles.comparison)
    setSelectedMatchId(demoMatches[0]?.id ?? null)
    setActiveMobileArticle('A')
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

  function handleArticleAModeChange(nextMode) {
    setArticleAMode(nextMode)
    setFormErrors((currentErrors) =>
      clearFieldError(currentErrors, 'articleA'),
    )
  }

  function handleArticleBModeChange(nextMode) {
    setArticleBMode(nextMode)
    setFormErrors((currentErrors) =>
      clearFieldError(currentErrors, 'articleB'),
    )
  }

  function handleArticleAFileChange(event) {
    setArticleAFile(event.target.files?.[0] ?? null)
    setFormErrors((currentErrors) =>
      clearFieldError(currentErrors, 'articleA'),
    )
  }

  function handleArticleBFileChange(event) {
    setArticleBFile(event.target.files?.[0] ?? null)
    setFormErrors((currentErrors) =>
      clearFieldError(currentErrors, 'articleB'),
    )
  }

  function validateArticleInput(mode, url, file) {
    if (mode === 'url') {
      return isValidHttpUrl(url)
        ? ''
        : 'Paste a complete article link beginning with http:// or https://.'
    }

    if (!file) {
      return 'Choose a PDF or Word document for this article.'
    }

    if (!isAllowedUpload(file)) {
      return 'Only .pdf and .docx files are supported.'
    }

    if (file.size > maxUploadSizeBytes) {
      return 'Use a file under 10MB.'
    }

    return ''
  }

  function buildCompareRequest() {
    const usesUpload = articleAMode === 'upload' || articleBMode === 'upload'

    if (!usesUpload) {
      return {
        endpoint: '/api/compare/stream',
        options: {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            article_a_url: articleAUrl.trim(),
            article_b_url: articleBUrl.trim(),
            focus,
          }),
        },
      }
    }

    const formData = new FormData()
    formData.append('focus', focus)

    if (articleAMode === 'url') {
      formData.append('article_a_url', articleAUrl.trim())
    } else {
      formData.append('article_a_file', articleAFile)
    }

    if (articleBMode === 'url') {
      formData.append('article_b_url', articleBUrl.trim())
    } else {
      formData.append('article_b_file', articleBFile)
    }

    return {
      endpoint: '/api/compare/files/stream',
      options: {
        method: 'POST',
        body: formData,
      },
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()

    const nextFormErrors = {
      articleA: validateArticleInput(articleAMode, articleAUrl, articleAFile),
      articleB: validateArticleInput(articleBMode, articleBUrl, articleBFile),
    }

    Object.keys(nextFormErrors).forEach((fieldName) => {
      if (!nextFormErrors[fieldName]) {
        delete nextFormErrors[fieldName]
      }
    })

    setFormErrors(nextFormErrors)

    if (Object.keys(nextFormErrors).length > 0) {
      setArticles([])
      setComparison(null)
      setSelectedMatchId(null)
      setActiveMobileArticle('A')
      setApiErrors([])
      setProgress(null)
      setUsingDemoCopy(false)
      setStatusMessage('')
      return
    }

    const isDemoPair =
      articleAMode === 'url' &&
      articleBMode === 'url' &&
      articleAUrl.trim() === demoArticles.urls.A &&
      articleBUrl.trim() === demoArticles.urls.B

    setIsLoading(true)
    setArticles([])
    setComparison(null)
    setSelectedMatchId(null)
    setActiveMobileArticle('A')
    setApiErrors([])
    setProgress({
      percent: 1,
      message: 'Starting comparison...',
      status: 'running',
    })
    setUsingDemoCopy(false)
    setStatusMessage('Preparing comparison...')

    try {
      const request = buildCompareRequest()
      const response = await fetch(request.endpoint, request.options)

      if (!response.ok) {
        const errorPayload = await response.json()
        throw new Error(parseApiError(errorPayload))
      }

      const data = await parseEventStream(response, (progressEvent) => {
        setProgress({
          percent: progressEvent.percent ?? 0,
          message: progressEvent.message ?? 'Processing...',
          status: progressEvent.status ?? 'running',
        })
      })

      const returnedArticles = data.articles ?? []
      const returnedErrors = data.errors ?? []
      const backendComparison = data.comparison ?? null
      const hasBackendMatches = getComparisonMatches(backendComparison).length > 0
      const displayComparison =
        hasBackendMatches || !isDemoPair
          ? backendComparison
          : demoArticles.comparison
      const displayMatches = getComparisonMatches(displayComparison)

      setArticles(returnedArticles)
      setApiErrors(returnedErrors)
      setComparison(displayComparison)
      setSelectedMatchId(displayMatches[0]?.id ?? null)
      setActiveMobileArticle('A')
      setProgress({
        percent: 100,
        message: data.processing?.message ?? 'Comparison finished.',
        status: 'completed',
      })

      if (returnedArticles.length > 0 && returnedErrors.length === 0) {
        if (displayMatches.length > 0 && !hasBackendMatches && isDemoPair) {
          setStatusMessage(
            'Live article text loaded. Demo Sprint 2 highlights are shown until backend comparison results are available.',
          )
        } else if (displayMatches.length > 0) {
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
          'Partial backend result loaded. One article could not be processed.',
        )
      } else {
        setStatusMessage('These articles could not be processed.')
      }
    } catch (error) {
      if (isDemoPair) {
        showOfflineDemoFallback(
          'Live backend was unavailable, so the offline demo copy was loaded.',
        )
      } else {
        setArticles([])
        setComparison(null)
        setSelectedMatchId(null)
        setActiveMobileArticle('A')
        setApiErrors([])
        setProgress(null)
        setUsingDemoCopy(false)
        setStatusMessage(
          `Could not complete the comparison. ${error.message}`,
        )
      }
    } finally {
      setIsLoading(false)
    }
  }

  const articleA = articles.find((article) => article.article_ref === 'A')
  const articleB = articles.find((article) => article.article_ref === 'B')
  const comparisonMatches = getComparisonMatches(comparison)
  const selectedMatch =
    comparisonMatches.find((match) => match.id === selectedMatchId) ?? null
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

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="Narrative Diff home">
          <span className="brand-mark" aria-hidden="true">
            ND
          </span>
          <span>Narrative Diff</span>
        </a>
        <span className="sprint-label">Sprint 2 prototype</span>
      </header>

      <main>
        <section className="hero-section">
          <p className="eyebrow">Compare reporting. See the difference.</p>
          <h1>How does the story change between news outlets?</h1>
          <p className="hero-copy">
            Compare two reports on the same story and see where they align,
            diverge, or leave details out.
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
              <ArticleSourceField
                side="A"
                title="First article"
                mode={articleAMode}
                url={articleAUrl}
                file={articleAFile}
                error={formErrors.articleA}
                isLoading={isLoading}
                onModeChange={handleArticleAModeChange}
                onUrlChange={handleArticleAUrlChange}
                onFileChange={handleArticleAFileChange}
              />

              <ArticleSourceField
                side="B"
                title="Second article"
                mode={articleBMode}
                url={articleBUrl}
                file={articleBFile}
                error={formErrors.articleB}
                isLoading={isLoading}
                onModeChange={handleArticleBModeChange}
                onUrlChange={handleArticleBUrlChange}
                onFileChange={handleArticleBFileChange}
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

        <section className="results-section" aria-labelledby="results-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Comparison view</p>
              <h2 id="results-title">Matched article evidence</h2>
            </div>
            <p>
              Review the source text and inspect highlighted similarities or
              differences.
            </p>
          </div>

          <div className="highlight-legend" aria-label="Highlight legend">
            {relationshipOptions.map((option) => (
              <span
                className={`legend-item legend-item--${option.value}`}
                key={option.value}
              >
                {option.label}
              </span>
            ))}
          </div>

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
                matches={comparisonMatches}
                visibleLabels={visibleLabels}
                selectedMatchId={selectedMatchId}
                onSelectMatch={setSelectedMatchId}
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
                matches={comparisonMatches}
                visibleLabels={visibleLabels}
                selectedMatchId={selectedMatchId}
                onSelectMatch={setSelectedMatchId}
              />
            </div>
          </div>

          <ComparisonControls
            matches={comparisonMatches}
            visibleLabels={visibleLabels}
            selectedMatch={selectedMatch}
            articleA={articleA}
            articleB={articleB}
            onToggleLabel={handleToggleLabel}
            onResetFilters={handleResetFilters}
          />

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
        <p>Highlighted evidence with explanations and filters.</p>
      </footer>
    </div>
  )
}

export default App
