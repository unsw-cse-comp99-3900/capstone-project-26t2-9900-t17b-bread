import { useEffect, useRef, useState } from 'react'
import {
  articleInputModes,
  authSessionKey,
  comparisonHistoryKey,
  demoIndexPath,
  focusOptions,
  friendlyErrorMessages,
  maxHistoryItems,
  maxUploadSizeBytes,
  minTextChars,
  relationshipOptions,
} from './config/appConfig'
import {
  copyTextToClipboard,
  createFileFromDemoAsset,
  downloadTextFile,
  getDownloadFilename,
  isAllowedUpload,
  isPdfFile,
  isValidHttpUrl,
  isValidText,
  isValidUpload,
  readTextDemoAsset,
} from './utils/appHelpers'
import './App.css'

function loadComparisonHistory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(comparisonHistoryKey) ?? '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveComparisonHistory(items) {
  localStorage.setItem(
    comparisonHistoryKey,
    JSON.stringify(items.slice(0, maxHistoryItems)),
  )
}

function loadAuthSession() {
  try {
    const parsed = JSON.parse(localStorage.getItem(authSessionKey) ?? 'null')
    return parsed?.accessToken && parsed?.user ? parsed : null
  } catch {
    return null
  }
}

function saveAuthSession(session) {
  if (!session) {
    localStorage.removeItem(authSessionKey)
    return
  }
  localStorage.setItem(authSessionKey, JSON.stringify(session))
}

function authHeaders(authToken) {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {}
}

async function parseJsonResponse(response) {
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload.detail || 'The request could not be completed.')
  }
  return payload
}

function isValidUsername(value) {
  const username = value.trim()
  return /^[a-zA-Z0-9_]{3,20}$/.test(username)
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function getHistoryArticleTitle(article, fallback) {
  return article?.title || article?.source_domain || fallback
}

function buildHistoryItem({ focus, articles, comparison }) {
  const savedAt = new Date().toISOString()
  const articleA = articles.find((article) => article.article_ref === 'A')
  const articleB = articles.find((article) => article.article_ref === 'B')
  const focusLabel = getFocusLabel(focus)

  return {
    id: `${Date.now()}`,
    saved_at: savedAt,
    focus,
    label: `${getHistoryArticleTitle(articleA, 'Article A')} vs ${getHistoryArticleTitle(
      articleB,
      'Article B',
    )}`,
    description: `${focusLabel} · ${new Date(savedAt).toLocaleString()}`,
    articles,
    comparison,
  }
}

function normalizeHistoryItem(item) {
  const focusLabel = getFocusLabel(item.focus)
  const savedAt = item.saved_at ?? new Date().toISOString()
  return {
    ...item,
    id: `${item.id ?? item.history_id ?? item.comparison_id ?? savedAt}`,
    saved_at: savedAt,
    description: `${focusLabel} - ${new Date(savedAt).toLocaleString()}`,
  }
}

function buildComparisonSummary({
  focus,
  articleA,
  articleB,
  matches,
  selectedMatch,
}) {
  const counts = getMatchCounts(matches)
  const lines = [
    'Narrative Diff comparison summary',
    `Focus: ${getFocusLabel(focus)}`,
    `Article A: ${getHistoryArticleTitle(articleA, 'Article A')}`,
    `Article B: ${getHistoryArticleTitle(articleB, 'Article B')}`,
    `Aligned: ${counts.aligned}`,
    `Partially aligned: ${counts.partially_aligned}`,
    `Divergent: ${counts.divergent}`,
  ]

  if (selectedMatch) {
    lines.push(
      '',
      `Selected pair: Pair ${selectedMatch.pairNumber}`,
      `Label: ${
        relationshipOptions.find((option) => option.value === selectedMatch.label)
          ?.label ?? selectedMatch.label
      }`,
      `Explanation: ${selectedMatch.explanation}`,
    )
  }

  return lines.join('\n')
}

function buildHtmlReport({
  focus,
  articleA,
  articleB,
  matches,
  counts,
  generatedAt,
}) {
  const relationshipLabel = (label) =>
    relationshipOptions.find((option) => option.value === label)?.label ?? label
  const totalPairs = matches.length
  const averageScore = getAverageMatchScore(matches)
  const averageScoreLabel =
    averageScore == null ? 'N/A' : `${Math.round(averageScore * 100)}%`
  const generatedLabel = new Date(generatedAt).toLocaleString()
  const reportLogo = `
    <svg class="brand-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="#192b45"/>
      <text x="5" y="43" fill="#f8f2e8" font-family="Inter, Arial, sans-serif" font-size="30" font-weight="800">N</text>
      <path d="M34 14v36" stroke="#f47a25" stroke-width="3.5" stroke-linecap="round"/>
      <text x="37" y="43" fill="#ffd9a8" font-family="Inter, Arial, sans-serif" font-size="30" font-weight="800">D</text>
    </svg>
  `

  const articleCard = (article, label) => {
    const title = getHistoryArticleTitle(article, label)
    const source = article?.source_domain || getUrlHost(article?.url ?? '')
    const sourceLine = source ? `<p class="source">${escapeHtml(source)}</p>` : ''
    const link = hasExternalArticleUrl(article)
      ? `<a class="article-link" href="${escapeHtml(article.url)}" target="_blank" rel="noreferrer">Open source article</a>`
      : '<span class="article-link article-link--muted">Local or uploaded source</span>'

    return `
      <section class="article-card">
        <span class="article-label">${escapeHtml(label)}</span>
        <h2>${escapeHtml(title)}</h2>
        ${sourceLine}
        ${link}
      </section>
    `
  }

  const matchBlocks = matches.length
    ? matches
        .map(
          (match) => `
            <article class="pair pair--${escapeHtml(match.label)}">
              <div class="pair-header">
                <div>
                  <strong>Pair ${escapeHtml(match.pairNumber ?? '')}</strong>
                  <span class="pill pill--${escapeHtml(match.label)}">${escapeHtml(relationshipLabel(match.label))}</span>
                </div>
                <em>Score ${Math.round(Number(match.score ?? 0) * 100)}%</em>
              </div>
              <p class="explanation">${escapeHtml(match.explanation ?? 'No explanation available.')}</p>
              <div class="evidence-grid">
                <section>
                  <h3>Article A</h3>
                  <p class="evidence-text">${escapeHtml(match.articleAText ?? match.a_text_preview ?? '')}</p>
                </section>
                <section>
                  <h3>Article B</h3>
                  <p class="evidence-text">${escapeHtml(match.articleBText ?? match.b_text_preview ?? '')}</p>
                </section>
              </div>
            </article>
          `,
        )
        .join('')
    : '<p class="empty">No matched evidence was returned for this comparison.</p>'

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Narrative Diff Comparison Report</title>
  <style>
    :root {
      color: #18243a;
      background: #f3f0e8;
      font-family: Inter, Arial, sans-serif;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      padding: 44px 22px;
      color: #18243a;
      background: #f3f0e8;
    }
    main {
      max-width: 1080px;
      margin: 0 auto;
      overflow: hidden;
      border: 1px solid #d8d2c4;
      border-radius: 22px;
      background: #fffdf8;
      box-shadow: 0 22px 70px rgba(24, 36, 58, 0.14);
    }
    .report-header {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      align-items: start;
      padding: 34px 36px 30px;
      border-bottom: 1px solid #e2dccf;
      background: linear-gradient(135deg, #fffaf1 0%, #ffffff 60%, #f0fbf7 100%);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
      font-weight: 850;
    }
    .brand-logo {
      width: 44px;
      height: 44px;
      flex: 0 0 auto;
      display: block;
    }
    .eyebrow {
      margin: 0 0 10px;
      color: #a94b17;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0 0 10px;
      font-family: Georgia, 'Times New Roman', serif;
      font-size: clamp(34px, 5vw, 54px);
      line-height: 1.02;
      font-weight: 500;
    }
    .meta {
      margin: 0;
      color: #627086;
      line-height: 1.55;
    }
    .meta-card {
      min-width: 240px;
      border: 1px solid #ddd7ca;
      border-radius: 16px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.78);
    }
    .meta-card dl {
      display: grid;
      gap: 12px;
      margin: 0;
    }
    .meta-card dt {
      color: #627086;
      font-size: 11px;
      font-weight: 850;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .meta-card dd {
      margin: 3px 0 0;
      font-weight: 850;
    }
    .content {
      padding: 32px 36px 38px;
    }
    .articles,
    .summary,
    .evidence-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }
    .article-card,
    .pair section {
      border: 1px solid #ddd7ca;
      border-radius: 16px;
      padding: 18px;
      background: #fff;
    }
    .article-label {
      display: inline-block;
      margin-bottom: 12px;
      border-radius: 999px;
      padding: 5px 9px;
      color: #18243a;
      background: #d9f4ec;
      font-size: 12px;
      font-weight: 900;
    }
    .article-card:nth-child(2) .article-label {
      background: #fde4ca;
    }
    h2,
    h3 {
      margin: 0 0 10px;
    }
    .article-card h2 {
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 24px;
      line-height: 1.15;
      font-weight: 500;
    }
    .source {
      margin: 0 0 14px;
      color: #627086;
      font-size: 14px;
    }
    .article-link {
      color: #a94b17;
      font-size: 14px;
      font-weight: 850;
      text-decoration: none;
    }
    .article-link--muted {
      color: #627086;
    }
    .summary {
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin: 24px 0;
    }
    .metric {
      display: grid;
      gap: 4px;
      border: 1px solid #e2dccf;
      border-radius: 16px;
      padding: 16px;
      background: #f8f6ef;
    }
    .metric span {
      color: #627086;
      font-size: 12px;
      font-weight: 850;
    }
    .metric strong {
      font-size: 28px;
    }
    .overview {
      margin: 0 0 28px;
      border: 1px solid #d7efe8;
      border-radius: 16px;
      padding: 18px;
      background: #ecfaf6;
      color: #1f4f45;
      line-height: 1.6;
    }
    .section-title {
      margin: 0 0 14px;
      font-family: Georgia, 'Times New Roman', serif;
      font-size: 30px;
      font-weight: 500;
    }
    .pair {
      margin-top: 18px;
      border: 1px solid #ddd7ca;
      border-left-width: 7px;
      border-radius: 18px;
      padding: 20px;
      background: #fff;
    }
    .pair--aligned {
      border-left-color: #2f8d74;
    }
    .pair--partially_aligned {
      border-left-color: #c17b13;
    }
    .pair--divergent {
      border-left-color: #bd4747;
    }
    .pair-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
    }
    .pair-header div {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }
    .pair-header strong,
    .pill,
    .pair-header em {
      border-radius: 999px;
      padding: 7px 11px;
      background: #f0eee7;
      font-style: normal;
      font-weight: 800;
    }
    .pair-header strong {
      color: #fff;
      background: #18243a;
    }
    .pill--aligned {
      background: #d9f4ec;
      color: #1f6c5c;
    }
    .pill--partially_aligned {
      background: #fff0c7;
      color: #80500a;
    }
    .pill--divergent {
      background: #fde2df;
      color: #94403d;
    }
    .explanation {
      color: #4b596f;
      line-height: 1.55;
    }
    p {
      line-height: 1.65;
    }
    .evidence-grid section {
      background: #fffdf8;
    }
    .evidence-text {
      margin: 0;
      color: #314057;
      white-space: pre-wrap;
    }
    .empty {
      border: 1px solid #ddd7ca;
      border-radius: 16px;
      padding: 18px;
      background: #fff;
      color: #627086;
    }
    @media print {
      body {
        padding: 0;
        background: #fff;
      }
      main {
        border: 0;
        border-radius: 0;
        box-shadow: none;
      }
      .pair {
        break-inside: avoid;
      }
    }
    @media (max-width: 760px) {
      body {
        padding: 18px;
      }
      .report-header,
      .content {
        padding: 24px;
      }
      .report-header {
        grid-template-columns: 1fr;
      }
      .articles,
      .summary,
      .evidence-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <header class="report-header">
      <div>
        <div class="brand">
          ${reportLogo}
          <span>Narrative Diff</span>
        </div>
        <p class="eyebrow">Comparison report</p>
        <h1>How the coverage compares</h1>
        <p class="meta">
          A readable export of the paragraph-level comparison result, including
          relationship labels, confidence scores, explanations, and source evidence.
        </p>
      </div>
      <aside class="meta-card" aria-label="Report metadata">
        <dl>
          <div>
            <dt>Generated</dt>
            <dd>${escapeHtml(generatedLabel)}</dd>
          </div>
          <div>
            <dt>Focus</dt>
            <dd>${escapeHtml(getFocusLabel(focus))}</dd>
          </div>
          <div>
            <dt>Average score</dt>
            <dd>${escapeHtml(averageScoreLabel)}</dd>
          </div>
        </dl>
      </aside>
    </header>

    <div class="content">
      <section class="articles" aria-label="Compared articles">
        ${articleCard(articleA, 'Article A')}
        ${articleCard(articleB, 'Article B')}
      </section>

      <section class="summary" aria-label="Relationship summary">
        <div class="metric"><span>Total pairs</span><strong>${totalPairs}</strong></div>
        <div class="metric"><span>Aligned</span><strong>${counts.aligned}</strong></div>
        <div class="metric"><span>Partially aligned</span><strong>${counts.partially_aligned}</strong></div>
        <div class="metric"><span>Divergent</span><strong>${counts.divergent}</strong></div>
      </section>

      <p class="overview">
        This report compares two articles at paragraph level. Use the relationship
        labels to quickly identify shared coverage, partial overlap, and divergent
        framing or claims.
      </p>

      <section>
        <p class="eyebrow">Matched evidence</p>
        <h2 class="section-title">Evidence pairs</h2>
        ${matchBlocks}
      </section>
    </div>
  </main>
</body>
</html>`
}

function getUrlHost(value) {
  try {
    return new URL(value.trim()).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

function isUploadedArticle(article) {
  return article?.source_type === 'upload' || article?.url?.startsWith('upload://')
}

function getUploadFileName(article) {
  if (!article?.url?.startsWith('upload://')) {
    return ''
  }

  try {
    return decodeURIComponent(article.url.replace('upload://', ''))
  } catch {
    return article.url.replace('upload://', '')
  }
}

function getFileStem(fileName) {
  return fileName.replace(/\.[^.]+$/, '').trim()
}

function getUploadedDocumentTitle(fileName) {
  const extension = fileName.split('.').pop()?.toLowerCase()

  if (extension === 'pdf') {
    return 'Uploaded PDF document'
  }

  if (extension === 'docx') {
    return 'Uploaded Word document'
  }

  return 'Uploaded document'
}

function isWeakUploadTitle(title, fileName) {
  const normalizedTitle = (title ?? '').trim().toLowerCase()
  const normalizedStem = getFileStem(fileName).toLowerCase()

  return (
    !normalizedTitle ||
    normalizedTitle === '(anonymous)' ||
    normalizedTitle === 'anonymous' ||
    normalizedTitle === 'untitled article' ||
    normalizedTitle === normalizedStem
  )
}

function getArticleDisplayTitle(article) {
  if (!isUploadedArticle(article)) {
    return article?.title ?? 'Untitled article'
  }

  const fileName = getUploadFileName(article)

  if (isWeakUploadTitle(article?.title, fileName)) {
    return getUploadedDocumentTitle(fileName)
  }

  return article.title
}

function hasExternalArticleUrl(article) {
  return /^https?:\/\//.test(article?.url ?? '')
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

function getMatchCounts(matches) {
  return relationshipOptions.reduce(
    (counts, option) => ({
      ...counts,
      [option.value]: matches.filter((match) => match.label === option.value).length,
    }),
    {},
  )
}

function getAverageMatchScore(matches) {
  const scores = matches
    .map((match) => Number(match.score))
    .filter((score) => Number.isFinite(score))

  if (scores.length === 0) {
    return null
  }

  return scores.reduce((total, score) => total + score, 0) / scores.length
}

function getDominantRelationship(counts) {
  return relationshipOptions.reduce(
    (dominant, option) =>
      counts[option.value] > counts[dominant.value] ? option : dominant,
    relationshipOptions[0],
  )
}

function buildReadableComparisonSummary(matches, backendSummary) {
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

function getMatchForParagraph(matches, side, paragraphIndex) {
  return matches.find((match) =>
    side === 'A'
      ? match.paragraphAIndex === paragraphIndex
      : match.paragraphBIndex === paragraphIndex,
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

function getParagraphText(article, paragraphIndex) {
  if (paragraphIndex == null) {
    return undefined
  }
  return article?.paragraphs?.[paragraphIndex]
}

function getMatchedText(article, match, side) {
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

      if (event === 'error') {
        throw new Error(
          data?.message ?? 'The backend could not complete the request.',
        )
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

function PdfToolbox({ file, pdfInfo, wordStatus, onConvertWord, isLoading }) {
  if (!isPdfFile(file)) {
    return null
  }

  const isImagePdf = pdfInfo?.is_image_based
  const typeLabel =
    pdfInfo == null
      ? null
      : isImagePdf
        ? 'Scanned / image PDF detected — OCR will be used.'
        : 'Text PDF detected — text can be read directly.'

  return (
    <div className="pdf-toolbox">
      {pdfInfo?.detecting && (
        <p className="input-hint">Checking whether this PDF is scanned...</p>
      )}
      {typeLabel && (
        <p className={`pdf-type-badge${isImagePdf ? ' pdf-type-badge--image' : ''}`}>
          {typeLabel}
        </p>
      )}
      {pdfInfo && !pdfInfo.ocr_available && isImagePdf && (
        <p className="input-hint input-hint--warn">
          OCR is not available on the server, so this scan may not be readable.
        </p>
      )}

      <button
        className="word-download-button"
        type="button"
        onClick={onConvertWord}
        disabled={isLoading || wordStatus?.state === 'loading'}
      >
        {wordStatus?.state === 'loading'
          ? 'Converting to Word...'
          : 'Download as Word (.docx)'}
      </button>

      {wordStatus?.state === 'success' && (
        <p className="input-hint input-hint--success">{wordStatus.message}</p>
      )}
      {wordStatus?.state === 'error' && (
        <p className="field-error">{wordStatus.message}</p>
      )}
    </div>
  )
}

function ArticleSourceField({
  side,
  title,
  mode,
  url,
  text,
  file,
  pdfInfo,
  wordStatus,
  error,
  isLoading,
  onModeChange,
  onUrlChange,
  onTextChange,
  onFileChange,
  onConvertWord,
  onClear,
}) {
  const inputId = `article-${side.toLowerCase()}-url`
  const textId = `article-${side.toLowerCase()}-text`
  const fileId = `article-${side.toLowerCase()}-file`
  const errorId = `article-${side.toLowerCase()}-error`
  const urlHost = getUrlHost(url)
  const labelTarget =
    mode === 'url' ? inputId : mode === 'text' ? textId : fileId

  return (
    <div className="field-group">
      <div className="field-header">
        <label htmlFor={labelTarget}>
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

      {mode === 'url' && (
        <>
          <div className="input-with-action">
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
            {url && (
              <button type="button" onClick={onClear} disabled={isLoading}>
                Clear
              </button>
            )}
          </div>
          {urlHost && <p className="input-hint">Source: {urlHost}</p>}
        </>
      )}

      {mode === 'text' && (
        <>
          <div className="input-with-action input-with-action--textarea">
            <textarea
              className="text-input"
              id={textId}
              value={text}
              onChange={onTextChange}
              rows={6}
              placeholder="Paste the full article text here..."
              aria-describedby={error ? errorId : undefined}
              aria-invalid={Boolean(error)}
              disabled={isLoading}
            />
            {text && (
              <button type="button" onClick={onClear} disabled={isLoading}>
                Clear
              </button>
            )}
          </div>
          <p className="input-hint">
            {text.trim().length} characters. Paste the article body directly —
            no link needed.
          </p>
        </>
      )}

      {mode === 'upload' && (
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
          {file && (
            <button
              className="clear-input-button"
              type="button"
              onClick={onClear}
              disabled={isLoading}
            >
              Clear file
            </button>
          )}
          <p className="input-hint">
            Works with text PDFs, scanned/image PDFs (auto OCR), Word files,
            paywalled pages, or subscription content.
          </p>
          <PdfToolbox
            file={file}
            pdfInfo={pdfInfo}
            wordStatus={wordStatus}
            onConvertWord={onConvertWord}
            isLoading={isLoading}
          />
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

            // Demo data highlights individual sentences; the live backend
            // returns paragraph-chunk-level matches, so we highlight the whole
            // paragraph in that case.
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

function ComparisonControls({
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

function ComparisonSummaryCard({ matches, backendSummary }) {
  if (matches.length === 0 && !backendSummary) {
    return null
  }

  const counts = getMatchCounts(matches)
  const averageScore = getAverageMatchScore(matches)
  const summaryText = buildReadableComparisonSummary(matches, backendSummary)
  const stats = [
    { label: 'Matched pairs', value: matches.length },
    { label: 'Aligned', value: counts.aligned },
    { label: 'Partially aligned', value: counts.partially_aligned },
    { label: 'Divergent', value: counts.divergent },
    {
      label: 'Average score',
      value: averageScore == null ? 'N/A' : `${Math.round(averageScore * 100)}%`,
    },
  ]

  return (
    <section className="comparison-summary" aria-label="Comparison summary">
      <div>
        <p className="eyebrow">High-level summary</p>
        <h3>Article difference overview</h3>
        <p>{summaryText}</p>
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

function MatchExplanationPanel({
  selectedMatch,
  matches,
  articleA,
  articleB,
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
        {typeof selectedMatch.score === 'number' && (
          <span className="match-score">
            Score {Math.round(selectedMatch.score * 100)}%
          </span>
        )}
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

function HistoryPanel({
  historyItems,
  isOpen,
  onClose,
  onRestore,
  onDelete,
  onClear,
  currentUser,
}) {
  if (!isOpen) {
    return null
  }

  return (
    <section className="history-panel" aria-label="Comparison history">
      <div className="history-panel__header">
        <div>
          <p className="eyebrow">{currentUser ? 'Account history' : 'Browser history'}</p>
          <h2>{currentUser ? 'Saved comparisons' : 'Recent comparisons'}</h2>
        </div>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>

      {historyItems.length > 0 ? (
        <>
          <div className="history-list">
            {historyItems.map((item) => (
              <div className="history-item" key={item.id}>
                <button type="button" onClick={() => onRestore(item)}>
                  <span>{item.label}</span>
                  <small>{item.description}</small>
                </button>
                <button
                  className="history-item__delete"
                  type="button"
                  onClick={() => onDelete(item.id)}
                  aria-label={`Delete ${item.label} from history`}
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
          <button className="history-clear-button" type="button" onClick={onClear}>
            Clear history
          </button>
        </>
      ) : (
        <p className="history-empty">
          {currentUser
            ? 'Saved comparisons will appear here after a successful run.'
            : 'Your recent comparisons will appear here after a successful run.'}
        </p>
      )}
    </section>
  )
}

function AuthModal({
  isOpen,
  mode,
  authForm,
  error,
  isSubmitting,
  onClose,
  onModeChange,
  onFormChange,
  onSubmit,
}) {
  if (!isOpen) {
    return null
  }

  const isRegister = mode === 'register'

  return (
    <div
      className="about-modal-backdrop"
      role="presentation"
      onMouseDown={onClose}
    >
      <section
        className="auth-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="about-modal__header">
          <div>
            <p className="eyebrow">Account</p>
            <h2 id="auth-title">{isRegister ? 'Create account' : 'Log in'}</h2>
          </div>
          <button
            className="about-modal__close"
            type="button"
            onClick={onClose}
            aria-label="Close login dialog"
          >
            x
          </button>
        </div>

        <form className="auth-form" onSubmit={onSubmit} noValidate>
          {isRegister && (
            <label>
              Display name
              <input
                value={authForm.displayName}
                onChange={(event) =>
                  onFormChange({ ...authForm, displayName: event.target.value })
                }
                placeholder="Optional display name"
              />
            </label>
          )}
          <label>
            Username
            <input
              type="text"
              value={authForm.username}
              onChange={(event) =>
                onFormChange({ ...authForm, username: event.target.value })
              }
              placeholder="Enter a UserName"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={authForm.password}
              onChange={(event) =>
                onFormChange({ ...authForm, password: event.target.value })
              }
              placeholder={isRegister ? 'At least 6 characters' : 'Password'}
            />
          </label>

          {error && <p className="auth-error">{error}</p>}

          <button className="compare-button auth-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Please wait...' : isRegister ? 'Create account' : 'Log in'}
          </button>
        </form>

        <button
          className="auth-switch"
          type="button"
          onClick={() => onModeChange(isRegister ? 'login' : 'register')}
        >
          {isRegister
            ? 'Already have an account? Log in'
            : 'New here? Create an account'}
        </button>
      </section>
    </div>
  )
}

function SaveOptionsModal({
  isOpen,
  currentUser,
  onClose,
  onDownloadHtml,
}) {
  if (!isOpen) {
    return null
  }

  return (
    <div
      className="about-modal-backdrop"
      role="presentation"
      onMouseDown={onClose}
    >
      <section
        className="save-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="save-options-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="about-modal__header">
          <div>
            <p className="eyebrow">Save result</p>
            <h2 id="save-options-title">Choose a local copy</h2>
          </div>
          <button
            className="about-modal__close"
            type="button"
            onClick={onClose}
            aria-label="Close save options"
          >
            x
          </button>
        </div>

        <p className="save-modal__copy">
          {currentUser
            ? 'This comparison is saved to your account history. You can also download a readable local report.'
            : 'Log in to save this comparison to account history, or download a readable local report.'}
        </p>

        <div className="save-modal__actions">
          <button className="compare-button" type="button" onClick={onDownloadHtml}>
            Download HTML report
          </button>
          <button className="header-pill-button" type="button" disabled>
            PDF coming soon
          </button>
        </div>
      </section>
    </div>
  )
}

function App() {
  const [articleAMode, setArticleAMode] = useState('url')
  const [articleBMode, setArticleBMode] = useState('url')
  const [articleAUrl, setArticleAUrl] = useState('')
  const [articleBUrl, setArticleBUrl] = useState('')
  const [articleAText, setArticleAText] = useState('')
  const [articleBText, setArticleBText] = useState('')
  const [articleAFile, setArticleAFile] = useState(null)
  const [articleBFile, setArticleBFile] = useState(null)
  const [pdfInfoA, setPdfInfoA] = useState(null)
  const [pdfInfoB, setPdfInfoB] = useState(null)
  const [wordStatusA, setWordStatusA] = useState(null)
  const [wordStatusB, setWordStatusB] = useState(null)
  const [focus, setFocus] = useState('general')
  const [formErrors, setFormErrors] = useState({})
  const [apiErrors, setApiErrors] = useState([])
  const [statusMessage, setStatusMessage] = useState('')
  const [progress, setProgress] = useState(null)
  const [articles, setArticles] = useState([])
  const [comparison, setComparison] = useState(null)
  const [comparisonId, setComparisonId] = useState(null)
  const [visibleLabels, setVisibleLabels] = useState(getInitialFilters)
  const [selectedMatchId, setSelectedMatchId] = useState(null)
  const [activeMobileArticle, setActiveMobileArticle] = useState('A')
  const [demoSamples, setDemoSamples] = useState([])
  const [demoLoadError, setDemoLoadError] = useState('')
  const [historyItems, setHistoryItems] = useState(loadComparisonHistory)
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [isSaveOptionsOpen, setIsSaveOptionsOpen] = useState(false)
  const [authSession, setAuthSession] = useState(loadAuthSession)
  const [isAuthOpen, setIsAuthOpen] = useState(false)
  const [authMode, setAuthMode] = useState('login')
  const [authForm, setAuthForm] = useState({
    displayName: '',
    username: '',
    password: '',
  })
  const [authError, setAuthError] = useState('')
  const [isAuthSubmitting, setIsAuthSubmitting] = useState(false)
  const [isAboutOpen, setIsAboutOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [showBackToTop, setShowBackToTop] = useState(false)
  const [backendStatus, setBackendStatus] = useState('offline')
  const resultsSectionRef = useRef(null)
  const backendFailureCountRef = useRef(0)
  const isLoadingRef = useRef(false)
  const authToken = authSession?.accessToken ?? ''
  const currentUser = authSession?.user ?? null
  function isSideReady(mode, url, text, file) {
    if (mode === 'url') {
      return isValidHttpUrl(url)
    }
    if (mode === 'text') {
      return isValidText(text)
    }
    return isValidUpload(file)
  }

  const canCompare =
    isSideReady(articleAMode, articleAUrl, articleAText, articleAFile) &&
    isSideReady(articleBMode, articleBUrl, articleBText, articleBFile)

  async function refreshAccountHistory(token = authToken) {
    if (!token) {
      setHistoryItems(loadComparisonHistory())
      return
    }

    const payload = await fetch('/api/history', {
      headers: authHeaders(token),
    }).then(parseJsonResponse)

    setHistoryItems((payload.items ?? []).map(normalizeHistoryItem))
  }

  useEffect(() => {
    isLoadingRef.current = isLoading
  }, [isLoading])

  useEffect(() => {
    let isActive = true

    async function loadAccountData() {
      if (!authToken) {
        setHistoryItems(loadComparisonHistory())
        return
      }

      try {
        const [mePayload, historyPayload] = await Promise.all([
          fetch('/api/auth/me', { headers: authHeaders(authToken) }).then(parseJsonResponse),
          fetch('/api/history', { headers: authHeaders(authToken) }).then(parseJsonResponse),
        ])

        if (!isActive) {
          return
        }

        const nextSession = { accessToken: authToken, user: mePayload }
        setAuthSession(nextSession)
        saveAuthSession(nextSession)
        setHistoryItems((historyPayload.items ?? []).map(normalizeHistoryItem))
      } catch {
        if (!isActive) {
          return
        }
        saveAuthSession(null)
        setAuthSession(null)
        setHistoryItems(loadComparisonHistory())
      }
    }

    loadAccountData()

    return () => {
      isActive = false
    }
  }, [authToken])

  useEffect(() => {
    let isActive = true

    async function loadDemoIndex() {
      try {
        const indexResponse = await fetch(demoIndexPath)

        if (!indexResponse.ok) {
          throw new Error('Demo index could not be loaded.')
        }

        const demoPaths = await indexResponse.json()
        const samples = await Promise.all(
          demoPaths.map(async (demoPath) => {
            const response = await fetch(demoPath)

            if (!response.ok) {
              throw new Error(`Demo metadata could not be loaded: ${demoPath}`)
            }

            return response.json()
          }),
        )

        if (isActive) {
          setDemoSamples(samples)
          setDemoLoadError('')
        }
      } catch (error) {
        if (isActive) {
          setDemoSamples([])
          setDemoLoadError(error.message)
        }
      }
    }

    loadDemoIndex()

    return () => {
      isActive = false
    }
  }, [])

  useEffect(() => {
    function handleWindowScroll() {
      setShowBackToTop(window.scrollY > 520)
    }

    handleWindowScroll()
    window.addEventListener('scroll', handleWindowScroll, { passive: true })

    return () => window.removeEventListener('scroll', handleWindowScroll)
  }, [])

  useEffect(() => {
    let isActive = true
    let timeoutId

    async function checkBackendStatus() {
      const controller = new AbortController()
      timeoutId = window.setTimeout(() => controller.abort(), 3500)

      try {
        const response = await fetch('/health', {
          cache: 'no-store',
          signal: controller.signal,
        })

        if (isActive && response.ok) {
          backendFailureCountRef.current = 0
          setBackendStatus('online')
        } else if (isActive) {
          backendFailureCountRef.current += 1
          if (backendFailureCountRef.current >= 3 && !isLoadingRef.current) {
            setBackendStatus('offline')
          }
        }
      } catch {
        if (isActive) {
          backendFailureCountRef.current += 1
          if (backendFailureCountRef.current >= 3 && !isLoadingRef.current) {
            setBackendStatus('offline')
          }
        }
      } finally {
        window.clearTimeout(timeoutId)
      }
    }

    checkBackendStatus()
    const intervalId = window.setInterval(checkBackendStatus, 30000)

    return () => {
      isActive = false
      window.clearTimeout(timeoutId)
      window.clearInterval(intervalId)
    }
  }, [])

  async function loadDemoSample(sample) {
    setIsLoading(true)
    setProgress(null)
    setArticles([])
    setComparison(null)
    setSelectedMatchId(null)
    setActiveMobileArticle('A')
    setApiErrors([])
    setFormErrors({})
    setPdfInfoA(null)
    setPdfInfoB(null)
    setWordStatusA(null)
    setWordStatusB(null)

    try {
      setFocus(sample.focus)

      if (sample.kind === 'url') {
        setArticleAMode('url')
        setArticleBMode('url')
        setArticleAUrl(sample.articleA.url)
        setArticleBUrl(sample.articleB.url)
        setArticleAText('')
        setArticleBText('')
        setArticleAFile(null)
        setArticleBFile(null)
      } else if (sample.kind === 'text') {
        const [articleAText, articleBText] = await Promise.all([
          readTextDemoAsset(sample.articleA),
          readTextDemoAsset(sample.articleB),
        ])

        setArticleAMode('text')
        setArticleBMode('text')
        setArticleAUrl('')
        setArticleBUrl('')
        setArticleAText(articleAText)
        setArticleBText(articleBText)
        setArticleAFile(null)
        setArticleBFile(null)
      } else {
        const [articleAFile, articleBFile] = await Promise.all([
          createFileFromDemoAsset(sample.articleA),
          createFileFromDemoAsset(sample.articleB),
        ])

        setArticleAMode('upload')
        setArticleBMode('upload')
        setArticleAUrl('')
        setArticleBUrl('')
        setArticleAText('')
        setArticleBText('')
        setArticleAFile(articleAFile)
        setArticleBFile(articleBFile)
        detectPdfType(articleAFile, setPdfInfoA)
        detectPdfType(articleBFile, setPdfInfoB)
      }

      setStatusMessage(`${sample.label} demo inputs loaded. Click Compare articles to run the backend.`)
    } catch (error) {
      setStatusMessage(`Could not load demo inputs. ${error.message}`)
    } finally {
      setIsLoading(false)
    }
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

  function handleArticleATextChange(event) {
    setArticleAText(event.target.value)
    setFormErrors((currentErrors) =>
      clearFieldError(currentErrors, 'articleA'),
    )
  }

  function handleArticleBTextChange(event) {
    setArticleBText(event.target.value)
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

  function clearArticleAInput() {
    setArticleAUrl('')
    setArticleAText('')
    setArticleAFile(null)
    setPdfInfoA(null)
    setWordStatusA(null)
    setFormErrors((currentErrors) =>
      clearFieldError(currentErrors, 'articleA'),
    )
  }

  function clearArticleBInput() {
    setArticleBUrl('')
    setArticleBText('')
    setArticleBFile(null)
    setPdfInfoB(null)
    setWordStatusB(null)
    setFormErrors((currentErrors) =>
      clearFieldError(currentErrors, 'articleB'),
    )
  }

  function resetComparisonWorkspace() {
    setArticleAMode('url')
    setArticleBMode('url')
    setArticleAUrl('')
    setArticleBUrl('')
    setArticleAText('')
    setArticleBText('')
    setArticleAFile(null)
    setArticleBFile(null)
    setPdfInfoA(null)
    setPdfInfoB(null)
    setWordStatusA(null)
    setWordStatusB(null)
    setFormErrors({})
    setApiErrors([])
    setProgress(null)
    setArticles([])
    setComparison(null)
    setComparisonId(null)
    setVisibleLabels(getInitialFilters())
    setSelectedMatchId(null)
    setActiveMobileArticle('A')
    setIsSaveOptionsOpen(false)
  }

  async function detectPdfType(file, setPdfInfo) {
    if (!isPdfFile(file)) {
      setPdfInfo(null)
      return
    }

    setPdfInfo({ detecting: true })

    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch('/api/upload/pdf-type', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        setPdfInfo(null)
        return
      }

      setPdfInfo(await response.json())
    } catch {
      setPdfInfo(null)
    }
  }

  function handleArticleAFileChange(event) {
    const file = event.target.files?.[0] ?? null
    setArticleAFile(file)
    setWordStatusA(null)
    setPdfInfoA(null)
    setFormErrors((currentErrors) =>
      clearFieldError(currentErrors, 'articleA'),
    )
    detectPdfType(file, setPdfInfoA)
  }

  function handleArticleBFileChange(event) {
    const file = event.target.files?.[0] ?? null
    setArticleBFile(file)
    setWordStatusB(null)
    setPdfInfoB(null)
    setFormErrors((currentErrors) =>
      clearFieldError(currentErrors, 'articleB'),
    )
    detectPdfType(file, setPdfInfoB)
  }

  async function convertPdfToWord(file, setWordStatus) {
    if (!isPdfFile(file)) {
      setWordStatus({
        state: 'error',
        message: 'Word conversion is only available for PDF files.',
      })
      return
    }

    setWordStatus({ state: 'loading' })

    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch('/api/upload/pdf-to-word', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        let message = 'The PDF could not be converted to Word.'
        try {
          const errorPayload = await response.json()
          const friendly = getFriendlyError(errorPayload?.detail ?? errorPayload)
          message = `${friendly.title}: ${friendly.message}`
        } catch {
          // keep default message
        }
        setWordStatus({ state: 'error', message })
        return
      }

      const blob = await response.blob()
      const filename = getDownloadFilename(
        response.headers.get('Content-Disposition'),
        `${file.name.replace(/\.pdf$/i, '')}.docx`,
      )

      const objectUrl = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = objectUrl
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(objectUrl)

      setWordStatus({
        state: 'success',
        message: `Saved "${filename}". Check your downloads folder.`,
      })
    } catch (error) {
      setWordStatus({
        state: 'error',
        message: `The PDF could not be converted to Word. ${error.message}`,
      })
    }
  }

  function validateArticleInput(mode, url, text, file) {
    if (mode === 'url') {
      return isValidHttpUrl(url)
        ? ''
        : 'Paste a complete article link beginning with http:// or https://.'
    }

    if (mode === 'text') {
      return isValidText(text)
        ? ''
        : `Paste at least ${minTextChars} characters of article text.`
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
      const body = { focus }

      if (articleAMode === 'text') {
        body.article_a_text = articleAText.trim()
      } else {
        body.article_a_url = articleAUrl.trim()
      }

      if (articleBMode === 'text') {
        body.article_b_text = articleBText.trim()
      } else {
        body.article_b_url = articleBUrl.trim()
      }

      return {
        endpoint: '/api/compare/stream',
        options: {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...authHeaders(authToken),
          },
          body: JSON.stringify(body),
        },
      }
    }

    const formData = new FormData()
    formData.append('focus', focus)

    if (articleAMode === 'url') {
      formData.append('article_a_url', articleAUrl.trim())
    } else if (articleAMode === 'text') {
      formData.append('article_a_text', articleAText.trim())
    } else {
      formData.append('article_a_file', articleAFile)
    }

    if (articleBMode === 'url') {
      formData.append('article_b_url', articleBUrl.trim())
    } else if (articleBMode === 'text') {
      formData.append('article_b_text', articleBText.trim())
    } else {
      formData.append('article_b_file', articleBFile)
    }

    return {
      endpoint: '/api/compare/files/stream',
      options: {
        method: 'POST',
        headers: authHeaders(authToken),
        body: formData,
      },
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()

    const nextFormErrors = {
      articleA: validateArticleInput(
        articleAMode,
        articleAUrl,
        articleAText,
        articleAFile,
      ),
      articleB: validateArticleInput(
        articleBMode,
        articleBUrl,
        articleBText,
        articleBFile,
      ),
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
      setComparisonId(null)
      setSelectedMatchId(null)
      setActiveMobileArticle('A')
      setApiErrors([])
      setProgress(null)
      setStatusMessage('')
      return
    }

    setIsLoading(true)
    setArticles([])
    setComparison(null)
    setComparisonId(null)
    setSelectedMatchId(null)
    setActiveMobileArticle('A')
    setApiErrors([])
    setProgress({
      percent: 1,
      message: 'Starting comparison...',
      status: 'running',
    })
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

      setArticles(returnedArticles)
      setApiErrors(returnedErrors)
      setComparison(backendComparison)
      setComparisonId(data.comparison_id ?? null)
      setSelectedMatchId(null)
      setActiveMobileArticle('A')
      setProgress({
        percent: 100,
        message: data.processing?.message ?? 'Comparison finished.',
        status: 'completed',
      })

      if (returnedArticles.length > 0 && returnedErrors.length === 0) {
        if (hasBackendMatches) {
          if (authToken) {
            await refreshAccountHistory(authToken)
          } else {
            const historyItem = buildHistoryItem({
              focus: data.focus ?? focus,
              articles: returnedArticles,
              comparison: backendComparison,
            })
            setHistoryItems((currentItems) => {
              const nextItems = [
                historyItem,
                ...currentItems.filter((item) => item.id !== historyItem.id),
              ].slice(0, maxHistoryItems)
              saveComparisonHistory(nextItems)
              return nextItems
            })
          }
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

      if (returnedArticles.length > 0) {
        window.requestAnimationFrame(scrollToResults)
      }
    } catch (error) {
      setArticles([])
      setComparison(null)
      setComparisonId(null)
      setSelectedMatchId(null)
      setActiveMobileArticle('A')
      setApiErrors([])
      setProgress(null)
      setStatusMessage(`Could not complete the comparison. ${error.message}`)
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
  const demoGroups = [
    {
      label: 'URL',
      samples: demoSamples.filter((sample) => sample.kind === 'url'),
    },
    {
      label: 'PDF',
      samples: demoSamples.filter(
        (sample) =>
          sample.kind === 'upload' &&
          sample.articleA?.fileName?.toLowerCase().endsWith('.pdf'),
      ),
    },
    {
      label: 'Word',
      samples: demoSamples.filter(
        (sample) =>
          sample.kind === 'upload' &&
          sample.articleA?.fileName?.toLowerCase().endsWith('.docx'),
      ),
    },
    {
      label: 'Text',
      samples: demoSamples.filter((sample) => sample.kind === 'text'),
    },
  ]

  function handleToggleLabel(label) {
    setVisibleLabels((currentLabels) => ({
      ...currentLabels,
      [label]: !currentLabels[label],
    }))
  }

  function handleResetFilters() {
    setVisibleLabels(getInitialFilters())
  }

  function handleSelectMatch(matchId) {
    setSelectedMatchId(matchId)
  }

  function handleRestoreHistory(item) {
    setArticles(item.articles ?? [])
    setComparison(item.comparison ?? null)
    setComparisonId(item.comparison_id ?? null)
    setFocus(item.focus ?? 'general')
    setSelectedMatchId(null)
    setActiveMobileArticle('A')
    setVisibleLabels(getInitialFilters())
    setApiErrors([])
    setProgress(null)
    setStatusMessage(`Restored comparison from ${new Date(item.saved_at).toLocaleString()}.`)
    setIsHistoryOpen(false)
  }

  async function handleClearHistory() {
    if (authToken) {
      try {
        await fetch('/api/history', {
          method: 'DELETE',
          headers: authHeaders(authToken),
        }).then(parseJsonResponse)
        setHistoryItems([])
        setStatusMessage('Account history cleared.')
      } catch (error) {
        setStatusMessage(`Could not clear account history. ${error.message}`)
      }
      return
    }

    saveComparisonHistory([])
    setHistoryItems([])
  }

  async function handleDeleteHistoryItem(itemId) {
    if (authToken) {
      try {
        await fetch(`/api/history/${itemId}`, {
          method: 'DELETE',
          headers: authHeaders(authToken),
        }).then(parseJsonResponse)
        await refreshAccountHistory(authToken)
        setStatusMessage('Saved comparison removed from account history.')
      } catch (error) {
        setStatusMessage(`Could not delete account history item. ${error.message}`)
      }
      return
    }

    setHistoryItems((currentItems) => {
      const nextItems = currentItems.filter((item) => item.id !== itemId)
      saveComparisonHistory(nextItems)
      return nextItems
    })
  }

  async function handleAuthSubmit(event) {
    event.preventDefault()
    setAuthError('')

    const username = authForm.username.trim()
    const password = authForm.password

    if (!username) {
    setAuthError('Enter a username.')
    return
  }

  if (!/^[a-zA-Z0-9_]{3,20}$/.test(username)) {
    setAuthError('Username must be 3–20 characters, letters/numbers/underscore only.')
    return
  }


    if (!password) {
      setAuthError('Enter your password.')
      return
    }

    if (authMode === 'register' && password.length < 6) {
      setAuthError('Use at least 6 characters for the password.')
      return
    }

    setIsAuthSubmitting(true)

    const endpoint =
      authMode === 'register' ? '/api/auth/register' : '/api/auth/login'
    const body = {
      username,
      password,
    }

    if (authMode === 'register') {
      body.display_name = authForm.displayName.trim()
    }

    try {
      const payload = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then(parseJsonResponse)

      const nextSession = {
        accessToken: payload.access_token,
        user: payload.user,
      }
      saveAuthSession(nextSession)
      setAuthSession(nextSession)
      setIsAuthOpen(false)
      setAuthForm({ displayName: '', username: '', password: '' })
      await refreshAccountHistory(payload.access_token)
      setStatusMessage(`Logged in as ${payload.user.display_name || payload.user.username}.`)
    } catch (error) {
      setAuthError(error.message)
    } finally {
      setIsAuthSubmitting(false)
    }
  }

  async function handleLogout() {
    if (authToken) {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: authHeaders(authToken),
      }).catch(() => {})
    }
    saveAuthSession(null)
    setAuthSession(null)
    resetComparisonWorkspace()
    setHistoryItems(loadComparisonHistory())
    setStatusMessage('Logged out. Browser history is shown locally.')
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
    if (!comparisonMatches.length) {
      return
    }

    const summary = buildComparisonSummary({
      focus,
      articleA,
      articleB,
      matches: comparisonMatches,
      selectedMatch,
    })
    await copyTextToClipboard(summary)
    setStatusMessage('Comparison summary copied to clipboard.')
  }

  async function saveCurrentResultToAccountHistory() {
    if (!authToken || !comparisonId) {
      return false
    }

    await fetch('/api/history', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(authToken),
      },
      body: JSON.stringify({ comparison_id: comparisonId }),
    }).then(parseJsonResponse)
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
        await saveCurrentResultToAccountHistory()
        setStatusMessage('Comparison saved to your account history.')
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
    const enrichedMatches = comparisonMatches.map((match) => ({
      ...match,
      articleAText: getMatchedText(articleA, match, 'A'),
      articleBText: getMatchedText(articleB, match, 'B'),
    }))
    const htmlReport = buildHtmlReport({
      focus,
      articleA,
      articleB,
      matches: enrichedMatches,
      counts: getMatchCounts(comparisonMatches),
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
          <button
            className="history-button"
            type="button"
            onClick={() => setIsHistoryOpen((isOpen) => !isOpen)}
          >
            History
            {historyItems.length > 0 && <span>{historyItems.length}</span>}
          </button>
          {currentUser ? (
            <>
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
              paragraph pairs, relationship labels, confidence scores, and
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
        <HistoryPanel
          historyItems={historyItems}
          isOpen={isHistoryOpen}
          onClose={() => setIsHistoryOpen(false)}
          onRestore={handleRestoreHistory}
          onDelete={handleDeleteHistoryItem}
          onClear={handleClearHistory}
          currentUser={currentUser}
        />

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
                mode={articleAMode}
                url={articleAUrl}
                text={articleAText}
                file={articleAFile}
                pdfInfo={pdfInfoA}
                wordStatus={wordStatusA}
                error={formErrors.articleA}
                isLoading={isLoading}
                onModeChange={handleArticleAModeChange}
                onUrlChange={handleArticleAUrlChange}
                onTextChange={handleArticleATextChange}
                onFileChange={handleArticleAFileChange}
                onConvertWord={() => convertPdfToWord(articleAFile, setWordStatusA)}
                onClear={clearArticleAInput}
              />

              <ArticleSourceField
                side="B"
                title="Second article"
                mode={articleBMode}
                url={articleBUrl}
                text={articleBText}
                file={articleBFile}
                pdfInfo={pdfInfoB}
                wordStatus={wordStatusB}
                error={formErrors.articleB}
                isLoading={isLoading}
                onModeChange={handleArticleBModeChange}
                onUrlChange={handleArticleBUrlChange}
                onTextChange={handleArticleBTextChange}
                onFileChange={handleArticleBFileChange}
                onConvertWord={() => convertPdfToWord(articleBFile, setWordStatusB)}
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
                  disabled={!comparisonMatches.length}
                >
                  Copy summary
                </button>
              </div>
            </div>
          </div>

          <ComparisonSummaryCard
            matches={comparisonMatches}
            backendSummary={comparison?.summary}
          />

          <ComparisonControls
            matches={comparisonMatches}
            visibleLabels={visibleLabels}
            onToggleLabel={handleToggleLabel}
            onResetFilters={handleResetFilters}
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

          {!selectedMatch && comparisonMatches.length > 0 && (
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
                  matches={comparisonMatches}
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
                  matches={comparisonMatches}
                  visibleLabels={visibleLabels}
                  selectedMatchId={selectedMatchId}
                  onSelectMatch={handleSelectMatch}
                />
              </div>
            </div>

            <div className="sticky-explanation-slot">
              <MatchExplanationPanel
                selectedMatch={selectedMatch}
                matches={comparisonMatches}
                articleA={articleA}
                articleB={articleB}
                onSelectMatch={handleSelectMatch}
                onClose={() => setSelectedMatchId(null)}
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
          <span aria-hidden="true">↑</span>
        </button>
      )}
    </div>
  )
}

export default App
