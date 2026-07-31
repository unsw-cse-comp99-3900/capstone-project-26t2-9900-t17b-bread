import { relationshipOptions } from '../config/appConfig'
import {
  formatPublicScore,
  getMatchedText,
  getScoreDetailItems,
} from '../utils/comparison'

export function MatchExplanationPanel({
  selectedMatch,
  matches,
  articleA,
  articleB,
  scoreGuides,
  onSelectMatch,
  onClose,
}) {
  if (!selectedMatch) {
    return null
  }

  const selectedIndex = matches.findIndex((match) => match.id === selectedMatch.id)
  const previousMatch = selectedIndex > 0 ? matches[selectedIndex - 1] : null
  const nextMatch =
    selectedIndex >= 0 && selectedIndex < matches.length - 1
      ? matches[selectedIndex + 1]
      : null

  return (
    <aside className="explanation-panel" aria-live="polite">
      <div className="explanation-panel__header">
        <span className="match-number">Pair {selectedMatch.pairNumber}</span>
        <span
          className={`relationship-pill relationship-pill--${selectedMatch.label}`}
        >
          {
            relationshipOptions.find(
              (option) => option.value === selectedMatch.label,
            )?.label
          }
        </span>
        <span className="match-score">
          Match {formatPublicScore(selectedMatch, 'match_strength')}
        </span>
        <button
          className="explanation-panel__close"
          type="button"
          onClick={onClose}
          aria-label="Close evidence panel"
        >
          Close
        </button>
      </div>

      <p>{selectedMatch.explanation}</p>

      <dl className="score-breakdown" aria-label="Score breakdown">
        {getScoreDetailItems(selectedMatch, scoreGuides).map((item) => (
          <div key={item.key} title={item.tooltip}>
            <dt>{item.label}</dt>
            <dd>
              {item.value}
              {item.level && <span>{item.level}</span>}
            </dd>
            {item.interpretation && <p>{item.interpretation}</p>}
            {item.disclaimer && <small>{item.disclaimer}</small>}
          </div>
        ))}
      </dl>

      <div className="match-nav">
        <button
          type="button"
          onClick={() => previousMatch && onSelectMatch(previousMatch.id)}
          disabled={!previousMatch}
        >
          Previous
        </button>
        <span>
          {selectedIndex + 1} of {matches.length}
        </span>
        <button
          type="button"
          onClick={() => nextMatch && onSelectMatch(nextMatch.id)}
          disabled={!nextMatch}
        >
          Next
        </button>
      </div>

      <div className="matched-text">
        <div>
          <strong>Article A</strong>
          <span>
            {getMatchedText(articleA, selectedMatch, 'A') ??
              'Matched text unavailable.'}
          </span>
        </div>
        <div>
          <strong>Article B</strong>
          <span>
            {getMatchedText(articleB, selectedMatch, 'B') ??
              'Matched text unavailable.'}
          </span>
        </div>
      </div>
    </aside>
  )
}
