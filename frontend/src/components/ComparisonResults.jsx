import { relationshipOptions } from '../config/appConfig'
import {
  buildReadableComparisonSummary,
  formatFactorName,
  formatScoreLevel,
  formatSummaryScore,
  getMatchCounts,
} from '../utils/comparison'

export function ComparisonControls({
  matches,
  visibleLabels,
  onToggleLabel,
  onResetFilters,
}) {
  if (matches.length === 0) {
    return null
  }

  const matchCounts = getMatchCounts(matches)

  return (
    <section className="comparison-filters" aria-label="Highlight filters">
      <p>Show:</p>
      <div className="filter-controls">
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
            <span>
              {option.label} {matchCounts[option.value]}
            </span>
          </label>
        ))}
      </div>

      <button className="reset-filters-button" type="button" onClick={onResetFilters}>
        Reset
      </button>
    </section>
  )
}

export function SortingControl({ options, selectedSort, onSelectSort }) {
  if (options.length === 0) {
    return null
  }

  return (
    <label className="sorting-control">
      <span>Sort by</span>
      <select
        value={selectedSort}
        onChange={(event) => onSelectSort(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.key} value={option.key}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export function ComparisonSummaryCard({
  matches,
  backendSummary,
  focus,
  selectedFactor,
  scoreGuides,
}) {
  if (matches.length === 0 && !backendSummary) {
    return null
  }

  const counts = getMatchCounts(matches)
  const summaryText = buildReadableComparisonSummary(matches, backendSummary)
  const factorGuide = scoreGuides?.factor_relevance ?? null
  const effectiveFactor =
    selectedFactor ??
    factorGuide?.factor ??
    matches.find((match) => match.factor_relevance?.factor)?.factor_relevance
      ?.factor ??
    (focus && focus !== 'general' ? focus : null)
  const factorName = effectiveFactor
    ? formatFactorName(effectiveFactor)
    : null
  const stats = [
    { label: 'Matched pairs', value: backendSummary?.match_count ?? matches.length },
    { label: 'Similar', value: backendSummary?.aligned_count ?? counts.aligned },
    {
      label: 'Partially similar',
      value: backendSummary?.partially_aligned_count ?? counts.partially_aligned,
    },
    { label: 'Divergent', value: backendSummary?.divergent_count ?? counts.divergent },
    {
      label: 'Avg match strength',
      value: formatSummaryScore(backendSummary, 'average_match_strength'),
    },
  ]

  if (backendSummary?.average_factor_relevance != null) {
    stats.push({
      label: factorGuide?.title
        ? `Avg ${factorGuide.title}`
        : factorName
          ? `Avg ${factorName} Relevance`
          : 'Avg Factor Relevance',
      value: formatSummaryScore(backendSummary, 'average_factor_relevance'),
    })
  }

  if (backendSummary?.average_stance_discrepancy != null) {
    stats.push({
      label: 'Avg stance discrepancy',
      value: formatSummaryScore(backendSummary, 'average_stance_discrepancy'),
    })
  }

  return (
    <section className="comparison-summary" aria-label="Comparison summary">
      <div>
        <p className="eyebrow">High-level summary</p>
        <h3>Article difference overview</h3>
        <p>{summaryText}</p>
        {factorName && (
          <div className="comparison-summary__factor">
            <span>
              {focus === 'general'
                ? 'Automatically selected factor'
                : 'Selected factor'}
            </span>
            <strong>{factorName}</strong>
            {factorGuide && (
              <details>
                <summary>{factorGuide.title ?? `${factorName} Relevance`} guide</summary>
                {factorGuide.question && <p>{factorGuide.question}</p>}
                {Array.isArray(factorGuide.bands) && factorGuide.bands.length > 0 && (
                  <ul>
                    {factorGuide.bands.map((band) => (
                      <li key={`${band.min}-${band.max}-${band.level}`}>
                        <strong>
                          {band.min}-{band.max}: {formatScoreLevel(band.level)}
                        </strong>
                        {band.interpretation && ` - ${band.interpretation}`}
                      </li>
                    ))}
                  </ul>
                )}
                {factorGuide.disclaimer && <small>{factorGuide.disclaimer}</small>}
              </details>
            )}
          </div>
        )}
      </div>
      <dl>
        {stats.map((item) => (
          <div key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

export function RelevanceNoticeModal({ notice, isOpen, onClose }) {
  if (!notice || !isOpen) {
    return null
  }

  const title = notice.title ?? 'Detailed comparison failed'
  const eyebrow = notice.eyebrow ?? 'Relevance check'
  const message =
    notice.action == null
      ? `${notice.message} Try another pair of articles about the same event if you want paragraph-level highlights.`
      : notice.message

  return (
    <div className="relevance-modal-backdrop" role="presentation">
      <section
        className="relevance-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="relevance-modal-title"
        aria-describedby="relevance-modal-message"
      >
        <p className="eyebrow">{eyebrow}</p>
        <h3 id="relevance-modal-title">{title}</h3>
        <p id="relevance-modal-message">{message}</p>
        {notice.action && <p>{notice.action}</p>}
        <button
          className="save-results-button"
          type="button"
          onClick={onClose}
        >
          Close
        </button>
      </section>
    </div>
  )
}
