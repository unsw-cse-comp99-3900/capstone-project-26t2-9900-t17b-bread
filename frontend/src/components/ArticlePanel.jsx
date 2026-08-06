import {
  getArticleDisplayTitle,
  getUploadFileName,
  hasExternalArticleUrl,
} from '../utils/article'
import { getFriendlyError } from '../utils/errors'
import {
  getMatchForParagraph,
  getMatchForSentence,
} from '../utils/comparison'

function HighlightedParagraph({
  paragraph,
  match,
  isVisible,
  isSelected,
  onSelectMatch,
}) {
  if (!isVisible) {
    return null
  }

  return (
    <button
      className={`comparison-highlight comparison-highlight--${match.label}${
        isSelected ? ' comparison-highlight--selected' : ''
      }`}
      type="button"
      onClick={() => onSelectMatch(match.id)}
      onFocus={() => onSelectMatch(match.id)}
      onMouseEnter={() => onSelectMatch(match.id)}
    >
      <span className="comparison-highlight__number">{match.pairNumber}</span>
      <span>{paragraph}</span>
    </button>
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

  return (
    <HighlightedParagraph
      paragraph={sentence.text}
      match={match}
      isVisible={isVisible}
      isSelected={isSelected}
      onSelectMatch={onSelectMatch}
    />
  )
}

function ParagraphBlock({ paragraph, match, isSelected, onSelectMatch }) {
  if (!match) {
    return <p className="article-paragraph">{paragraph}</p>
  }

  return (
    <p className="article-paragraph">
      <button
        className={`comparison-highlight comparison-paragraph comparison-highlight--${match.label}${
          isSelected ? ' comparison-highlight--selected' : ''
        }`}
        type="button"
        onClick={() => onSelectMatch(match.id)}
      >
        {paragraph}
      </button>
    </p>
  )
}

export function ArticlePanel({
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
    const displayTitle = getArticleDisplayTitle(article)
    const uploadFileName = getUploadFileName(article)
    const canOpenOriginal = hasExternalArticleUrl(article)
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
            <h2>{displayTitle}</h2>
          </div>
        </div>

        {canOpenOriginal && (
          <a
            className="article-source-link"
            href={article.url}
            target="_blank"
            rel="noreferrer"
          >
            View original article <span aria-hidden="true">-&gt;</span>
          </a>
        )}

        {!canOpenOriginal && uploadFileName && (
          <p className="article-source-note">Uploaded file: {uploadFileName}</p>
        )}

        <div className="article-copy">
          {article.paragraphs?.map((paragraph, paragraphIndex) => {
            const paragraphSentences = sentencesByParagraph[paragraphIndex] ?? []
            const hasSentenceMatch = paragraphSentences.some((sentence) =>
              getMatchForSentence(matches, side, sentence.id),
            )

            if (!hasSentenceMatch) {
              const paragraphMatch = getMatchForParagraph(
                matches,
                side,
                paragraphIndex,
              )
              const visibleMatch =
                paragraphMatch && visibleLabels[paragraphMatch.label]
                  ? paragraphMatch
                  : null

              return (
                <ParagraphBlock
                  key={paragraphIndex}
                  paragraph={paragraph}
                  match={visibleMatch}
                  isSelected={visibleMatch?.id === selectedMatchId}
                  onSelectMatch={onSelectMatch}
                />
              )
            }

            return (
              <p key={paragraphIndex} className="article-paragraph">
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
