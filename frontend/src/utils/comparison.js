import { focusOptions, relationshipOptions } from '../config/appConfig'

export function getFocusLabel(focusValue) {
  return (
    focusOptions.find((option) => option.value === focusValue)?.label ??
    'General comparison'
  )
}

export function getErrorForArticle(apiErrors, side) {
  return apiErrors.find((error) => error.article_ref === side)
}

export function getInitialFilters() {
  return relationshipOptions.reduce(
    (filters, option) => ({ ...filters, [option.value]: true }),
    {},
  )
}

export function getMatchCounts(matches) {
  return relationshipOptions.reduce(
    (counts, option) => ({
      ...counts,
      [option.value]: matches.filter((match) => match.label === option.value).length,
    }),
    {},
  )
}

export function getPublicScoreValue(match, scoreKey) {
  const score = Number(match?.[scoreKey]?.score)
  return Number.isFinite(score) ? score : null
}

export function formatPublicScore(match, scoreKey, fallbackLabel = 'N/A') {
  const score = getPublicScoreValue(match, scoreKey)
  return score == null ? fallbackLabel : `${score.toFixed(1)}/20`
}

export function formatSummaryScore(summary, scoreKey) {
  const score = Number(summary?.[scoreKey])
  return Number.isFinite(score) ? `${score.toFixed(1)}/20` : 'N/A'
}

export function formatScoreLevel(level) {
  if (!level) {
    return ''
  }

  return String(level)
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function formatFactorName(factor, fallbackLabel = 'Unknown') {
  const value = String(factor ?? '').trim()

  if (!value) {
    return fallbackLabel
  }

  return value
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function formatReasonCode(reasonCode) {
  if (!reasonCode) {
    return ''
  }

  const reasonText = String(reasonCode).trim()
  const readableReasons = {
    high_semantic_overlap:
      'The paragraphs cover very similar information.',
    strong_semantic_match:
      'The paragraphs discuss the same core content.',
    semantic_match:
      'The paragraphs discuss related content.',
    semantic_match_with_lexical_difference:
      'The paragraphs discuss similar content but use different wording.',
    lexical_overlap:
      'The paragraphs share important wording or named entities.',
    partial_overlap:
      'The paragraphs overlap in topic but differ in detail or emphasis.',
    shared_entities:
      'The paragraphs refer to the same people, places, organisations, or event details.',
    framing_difference:
      'The paragraphs cover related content with a different framing or emphasis.',
    stance_or_framing_difference:
      'The paragraphs describe related content with a different stance or framing.',
    divergent_framing:
      'The paragraphs describe related content but frame it differently.',
    contradiction_detected:
      'The paragraphs contain claims that may conflict with each other.',
    low_similarity:
      'The paragraphs only share limited context or weak similarity.',
    strong_shared_content_with_additional_detail:
      'The paragraphs share the same core content, while one side includes additional detail.',
    strong_similarity_with_nli_entailment:
      'The paragraphs make very similar claims about the same content.',
    related_content_with_nli_neutrality:
      'The paragraphs discuss related content, but neither paragraph clearly supports or conflicts with the other.',
    accepted_mapping_with_moderate_alignment:
      'The paragraphs are related enough to compare, but the connection is moderate.',
    strong_similarity_with_partial_nli_support:
      'The paragraphs are strongly related, but only part of the meaning matches directly.',
    strong_similarity_without_meaningful_contradiction:
      'The paragraphs are strongly related and do not show a clear conflict.',
    bidirectional_nli_contradiction:
      'The paragraphs appear to make conflicting claims.',
    contradiction_is_dominant:
      'The main relationship between these paragraphs is a possible conflict.',
  }

  return (
    readableReasons[reasonText] ??
    'The comparison model matched these paragraphs based on their content.'
  )
}

export function getScoreGuide(scoreGuides, scoreKey) {
  return scoreGuides?.[scoreKey] ?? null
}

export function getScoreGuideTitle(scoreGuides, scoreKey, fallbackLabel) {
  return getScoreGuide(scoreGuides, scoreKey)?.title ?? fallbackLabel
}

export function buildScoreGuideTooltip(scoreGuide) {
  if (!scoreGuide) {
    return ''
  }

  const bands = Array.isArray(scoreGuide.bands)
    ? scoreGuide.bands
        .map((band) => `${band.min}-${band.max}: ${formatScoreLevel(band.level)}`)
        .join('; ')
    : ''

  return [scoreGuide.question, bands, scoreGuide.disclaimer]
    .filter(Boolean)
    .join(' ')
}

export function getScoreDetailItems(match, scoreGuides) {
  const matchStrengthGuide = getScoreGuide(scoreGuides, 'match_strength')
  const stanceDiscrepancyGuide = getScoreGuide(
    scoreGuides,
    'stance_discrepancy',
  )
  const items = [
    {
      key: 'match_strength',
      label: getScoreGuideTitle(scoreGuides, 'match_strength', 'Match strength'),
      value: formatPublicScore(match, 'match_strength'),
      level: formatScoreLevel(match?.match_strength?.level),
      interpretation: match?.match_strength?.interpretation,
      disclaimer: matchStrengthGuide?.disclaimer,
      tooltip: buildScoreGuideTooltip(matchStrengthGuide),
    },
    {
      key: 'stance_discrepancy',
      label: getScoreGuideTitle(
        scoreGuides,
        'stance_discrepancy',
        'Stance discrepancy',
      ),
      value: formatPublicScore(match, 'stance_discrepancy'),
      level: formatScoreLevel(match?.stance_discrepancy?.level),
      interpretation: match?.stance_discrepancy?.interpretation,
      disclaimer:
        match?.stance_discrepancy?.disclaimer ??
        stanceDiscrepancyGuide?.disclaimer,
      tooltip: buildScoreGuideTooltip(stanceDiscrepancyGuide),
    },
  ]

  if (match?.factor_relevance) {
    const factorRelevanceGuide = getScoreGuide(scoreGuides, 'factor_relevance')
    items.splice(1, 0, {
      key: 'factor_relevance',
      label: getScoreGuideTitle(
        scoreGuides,
        'factor_relevance',
        `${formatFactorName(match.factor_relevance.factor, 'Factor')} Relevance`,
      ),
      value: formatPublicScore(match, 'factor_relevance'),
      level: formatScoreLevel(match.factor_relevance.level),
      interpretation: match.factor_relevance.interpretation,
      disclaimer: factorRelevanceGuide?.disclaimer,
      tooltip: buildScoreGuideTooltip(factorRelevanceGuide),
    })
  }

  return items
}

export function getDominantRelationship(counts) {
  return relationshipOptions.reduce(
    (dominant, option) =>
      counts[option.value] > counts[dominant.value] ? option : dominant,
    relationshipOptions[0],
  )
}

export function buildReadableComparisonSummary(matches, backendSummary) {
  if (typeof backendSummary?.statement === 'string' && backendSummary.statement) {
    return backendSummary.statement
  }

  if (typeof backendSummary?.text === 'string' && backendSummary.text) {
    return backendSummary.text
  }

  if (typeof backendSummary?.description === 'string' && backendSummary.description) {
    return backendSummary.description
  }

  if (matches.length === 0) {
    return 'No matched paragraph evidence is available yet. Run a comparison to generate a high-level summary.'
  }

  const counts = getMatchCounts(matches)
  const dominant = getDominantRelationship(counts)
  const dominantLabel = dominant.label.toLowerCase()
  const remaining = relationshipOptions
    .filter((option) => option.value !== dominant.value && counts[option.value] > 0)
    .map((option) => `${counts[option.value]} ${option.label.toLowerCase()}`)
    .join(' and ')

  if (!remaining) {
    return `${matches.length} paragraph pair${
      matches.length === 1 ? '' : 's'
    } found. The visible evidence is mostly ${dominantLabel}.`
  }

  return `${matches.length} paragraph pair${
    matches.length === 1 ? '' : 's'
  } found. The visible evidence is mostly ${dominantLabel}, with ${remaining} also shown.`
}

export function buildRelevanceNotice(response) {
  if (response?.relevant !== false) {
    return null
  }

  return {
    message:
      response.message ||
      'The articles are not relevant enough for detailed comparison.',
  }
}

export function getSortingOptions(comparison) {
  const options = comparison?.sorting?.options
  return Array.isArray(options) ? options : []
}

export function getDefaultSortKey(comparison) {
  return comparison?.sorting?.default ?? getSortingOptions(comparison)[0]?.key ?? ''
}

export function getValueAtPath(source, path) {
  if (!path) {
    return null
  }

  return path.split('.').reduce((current, key) => current?.[key], source)
}

export function compareNullableNumbers(valueA, valueB, direction = 'descending') {
  const numberA = Number(valueA)
  const numberB = Number(valueB)
  const hasA = Number.isFinite(numberA)
  const hasB = Number.isFinite(numberB)

  if (!hasA && !hasB) {
    return 0
  }

  if (!hasA) {
    return 1
  }

  if (!hasB) {
    return -1
  }

  return direction === 'ascending' ? numberA - numberB : numberB - numberA
}

export function sortMatchesByBackendOption(matches, sortingOption) {
  if (!sortingOption) {
    return matches
  }

  const primaryPath =
    sortingOption.score_path ?? sortingOption.path ?? sortingOption.primary_path
  const secondaryPath =
    sortingOption.secondary_score_path ??
    sortingOption.secondary_path ??
    sortingOption.tie_breaker_path
  const direction = sortingOption.direction ?? 'descending'
  const secondaryDirection = sortingOption.secondary_direction ?? direction

  // Use the backend score paths and the secondary score as a tie-breaker.
  return [...matches].sort((matchA, matchB) => {
    const primaryComparison = compareNullableNumbers(
      getValueAtPath(matchA, primaryPath),
      getValueAtPath(matchB, primaryPath),
      direction,
    )

    if (primaryComparison !== 0) {
      return primaryComparison
    }

    const secondaryComparison = compareNullableNumbers(
      getValueAtPath(matchA, secondaryPath),
      getValueAtPath(matchB, secondaryPath),
      secondaryDirection,
    )

    if (secondaryComparison !== 0) {
      return secondaryComparison
    }

    return (matchA.pairNumber ?? 0) - (matchB.pairNumber ?? 0)
  })
}

export function normalizeLabel(label) {
  if (label === 'partial') {
    return 'partially_aligned'
  }
  return relationshipOptions.some((option) => option.value === label)
    ? label
    : 'partially_aligned'
}

export function normalizeMatch(match, index) {
  // Older saved results use different field names, so normalize both response formats.
  const label = normalizeLabel(match.label ?? match.relationship)
  const paragraphAIndex =
    match.a_paragraph_index ??
    match.aParagraphIndex ??
    match.article_a_paragraph_index ??
    match.paragraph_a_index ??
    match.left_paragraph_index
  const paragraphBIndex =
    match.b_paragraph_index ??
    match.bParagraphIndex ??
    match.article_b_paragraph_index ??
    match.paragraph_b_index ??
    match.right_paragraph_index
  const chunkAId =
    match.a_chunk_id ??
    match.article_a_chunk_id ??
    match.chunk_a_id ??
    match.left_chunk_id
  const chunkBId =
    match.b_chunk_id ??
    match.article_b_chunk_id ??
    match.chunk_b_id ??
    match.right_chunk_id
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

  const aParagraphIndex = paragraphAIndex ?? null
  const bParagraphIndex = paragraphBIndex ?? null

  return {
    ...match,
    id:
      match.id ??
      `${chunkAId ?? sentenceAId ?? 'A'}-${chunkBId ?? sentenceBId ?? 'B'}-${index}`,
    label,
    paragraphAIndex,
    paragraphBIndex,
    chunkAId,
    chunkBId,
    pairNumber: match.pair_number ?? match.pairNumber ?? index + 1,
    sentenceAId,
    sentenceBId,
    aParagraphIndex,
    bParagraphIndex,
    aTextPreview: match.a_text_preview ?? match.aTextPreview ?? null,
    bTextPreview: match.b_text_preview ?? match.bTextPreview ?? null,
    reasonCode: match.reason_code ?? match.reasonCode ?? null,
    explanation:
      match.explanation ??
      'This match was returned by the comparison pipeline.',
  }
}

export function getComparisonMatches(comparison) {
  return (comparison?.matches ?? comparison?.alignments ?? []).map(
    normalizeMatch,
  )
}

export function getMatchForParagraph(matches, side, paragraphIndex) {
  return matches.find((match) =>
    side === 'A'
      ? match.paragraphAIndex === paragraphIndex
      : match.paragraphBIndex === paragraphIndex,
  )
}

export function getMatchForSentence(matches, side, sentenceId) {
  return matches.find((match) =>
    side === 'A'
      ? match.sentenceAId === sentenceId
      : match.sentenceBId === sentenceId,
  )
}

export function getSentenceText(article, sentenceId) {
  return article?.sentences?.find((sentence) => sentence.id === sentenceId)?.text
}

export function getParagraphText(article, paragraphIndex) {
  if (paragraphIndex == null) {
    return undefined
  }
  return article?.paragraphs?.[paragraphIndex]
}

export function getMatchedText(article, match, side) {
  const preview = side === 'A' ? match.aTextPreview : match.bTextPreview
  const paragraphIndex =
    side === 'A' ? match.paragraphAIndex : match.paragraphBIndex
  const sentenceId = side === 'A' ? match.sentenceAId : match.sentenceBId

  return (
    getParagraphText(article, paragraphIndex) ??
    getSentenceText(article, sentenceId) ??
    preview
  )
}

export function getCompareReadinessMessage(canCompare, isLoading) {
  if (isLoading || canCompare) {
    return ''
  }

  return 'Add two valid article sources to compare.'
}

