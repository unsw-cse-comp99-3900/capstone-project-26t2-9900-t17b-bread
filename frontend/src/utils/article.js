import { getFocusLabel } from './comparison'

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

export function getHistoryArticleTitle(article, fallback) {
  return article?.title || article?.source_domain || fallback
}

export function normalizeHistoryItem(item) {
  const focusLabel = getFocusLabel(item.focus)
  const savedAt = item.saved_at ?? new Date().toISOString()
  return {
    ...item,
    id: `${item.id ?? item.history_id ?? item.comparison_id ?? savedAt}`,
    saved_at: savedAt,
    description:
      item.description ?? `${focusLabel} - ${new Date(savedAt).toLocaleString()}`,
  }
}

export function getUrlHost(value) {
  try {
    return new URL(value.trim()).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

export function isUploadedArticle(article) {
  return article?.source_type === 'upload' || article?.url?.startsWith('upload://')
}

export function getUploadFileName(article) {
  if (!article?.url?.startsWith('upload://')) {
    return ''
  }

  try {
    return decodeURIComponent(article.url.replace('upload://', ''))
  } catch {
    return article.url.replace('upload://', '')
  }
}

export function getFileStem(fileName) {
  return fileName.replace(/\.[^.]+$/, '').trim()
}

export function getUploadedDocumentTitle(fileName) {
  const extension = fileName.split('.').pop()?.toLowerCase()

  if (extension === 'pdf') {
    return 'Uploaded PDF document'
  }

  if (extension === 'docx') {
    return 'Uploaded Word document'
  }

  return 'Uploaded document'
}

export function isWeakUploadTitle(title, fileName) {
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

export function getArticleDisplayTitle(article) {
  if (!isUploadedArticle(article)) {
    return article?.title ?? 'Untitled article'
  }

  const fileName = getUploadFileName(article)

  if (isWeakUploadTitle(article?.title, fileName)) {
    return getUploadedDocumentTitle(fileName)
  }

  return article.title
}

export function hasExternalArticleUrl(article) {
  return /^https?:\/\//.test(article?.url ?? '')
}

