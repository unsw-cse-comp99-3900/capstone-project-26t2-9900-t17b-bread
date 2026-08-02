import { relationshipOptions } from '../config/appConfig'
import { escapeHtml, getHistoryArticleTitle, getUrlHost, hasExternalArticleUrl } from './article'
import {
  formatPublicScore,
  formatReasonCode,
  formatSummaryScore,
  getMatchCounts,
  getScoreDetailItems,
  getFocusLabel,
} from './comparison'

export function buildComparisonSummary({
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
    `Similar: ${counts.aligned}`,
    `Partially similar: ${counts.partially_aligned}`,
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
    if (selectedMatch.reasonCode) {
      lines.push(`Reason: ${formatReasonCode(selectedMatch.reasonCode)}`)
    }
  }

  return lines.join('\n')
}

export function buildHtmlReport({
  focus,
  articleA,
  articleB,
  matches,
  counts,
  summary,
  scoreGuides,
  generatedAt,
}) {
  const relationshipLabel = (label) =>
    relationshipOptions.find((option) => option.value === label)?.label ?? label
  const totalPairs = matches.length
  const averageScoreLabel =
    formatSummaryScore(summary, 'average_match_strength')
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
          (match) => {
            const scoreDetails = getScoreDetailItems(match, scoreGuides)
              .map(
                (item) => `
                  <div title="${escapeHtml(item.tooltip)}">
                    <dt>${escapeHtml(item.label)}</dt>
                    <dd>
                      ${escapeHtml(item.value)}
                      ${item.level ? `<span>${escapeHtml(item.level)}</span>` : ''}
                    </dd>
                    ${item.interpretation ? `<p>${escapeHtml(item.interpretation)}</p>` : ''}
                  </div>
                `,
              )
              .join('')

            return `
            <article class="pair pair--${escapeHtml(match.label)}">
              <div class="pair-header">
                <div>
                  <strong>Pair ${escapeHtml(match.pairNumber ?? '')}</strong>
                  <span class="pill pill--${escapeHtml(match.label)}">${escapeHtml(relationshipLabel(match.label))}</span>
                </div>
                <em>Match ${escapeHtml(formatPublicScore(match, 'match_strength'))}</em>
              </div>
              <p class="explanation">${escapeHtml(match.explanation ?? 'No explanation available.')}</p>
              ${
                match.reasonCode
                  ? `<p class="reason"><strong>Reason:</strong> ${escapeHtml(formatReasonCode(match.reasonCode))}</p>`
                  : ''
              }
              <dl class="score-list">${scoreDetails}</dl>
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
          `
          },
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
    .reason {
      margin-top: 10px;
      padding: 10px 12px;
      border: 1px solid #e2dccf;
      border-radius: 12px;
      color: #4b596f;
      background: #f8f6ef;
    }
    .reason strong {
      color: #172238;
    }
    .score-list {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 14px 0 18px;
      padding: 0;
    }
    .score-list div {
      border: 1px solid #e2dccf;
      border-radius: 14px;
      padding: 12px;
      background: #f8f6ef;
    }
    .score-list p {
      margin: 8px 0 0;
      color: #627086;
      font-size: 13px;
    }
    .score-list dt {
      color: #627086;
      font-size: 11px;
      font-weight: 850;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .score-list dd {
      margin: 4px 0 0;
      font-weight: 850;
    }
    .score-list dd span {
      display: block;
      margin-top: 4px;
      color: #627086;
      font-size: 12px;
      font-weight: 700;
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
      .evidence-grid,
      .score-list {
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
          relationship labels, 0-20 scores, explanations, and source evidence.
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
            <dt>Average match strength</dt>
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
        <div class="metric"><span>Similar</span><strong>${counts.aligned}</strong></div>
        <div class="metric"><span>Partially similar</span><strong>${counts.partially_aligned}</strong></div>
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

