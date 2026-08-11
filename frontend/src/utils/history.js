function normalizeHistoryValue(value) {
  return String(value ?? '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase()
}

function normalizeHistoryUrl(value) {
  const rawValue = String(value ?? '').trim()

  if (!rawValue) {
    return ''
  }

  if (rawValue.startsWith('upload://')) {
    return normalizeHistoryValue(rawValue)
  }

  try {
    const url = new URL(rawValue)
    url.hash = ''
    url.search = ''
    url.hostname = url.hostname.replace(/^www\./, '').toLowerCase()
    return url.toString().replace(/\/$/, '')
  } catch {
    return normalizeHistoryValue(rawValue)
  }
}

export function getArticleHistoryKey(article) {
  const urlKey = normalizeHistoryUrl(article?.url)
  if (urlKey) {
    return urlKey
  }

  const titleKey = normalizeHistoryValue(article?.title ?? article?.source_domain)
  if (titleKey) {
    return titleKey
  }

  return normalizeHistoryValue(article?.id)
}

function getHistoryPairArticles(item) {
  const articles = Array.isArray(item?.articles) ? item.articles : []
  const articleA =
    articles.find((article) => article.article_ref === 'A') ?? articles[0]
  const articleB =
    articles.find((article) => article.article_ref === 'B') ?? articles[1]

  return [articleA, articleB]
}

export function getComparisonHistoryKey({ articles, articleA, articleB, focus }) {
  const source = Array.isArray(articles) ? { articles } : null
  const [resolvedA, resolvedB] = source
    ? getHistoryPairArticles(source)
    : [articleA, articleB]
  const articleAKey = getArticleHistoryKey(resolvedA)
  const articleBKey = getArticleHistoryKey(resolvedB)

  if (!articleAKey || !articleBKey) {
    return ''
  }

  // Focus is included because the same article pair can have different comparisons.
  return `${normalizeHistoryValue(focus ?? 'general')}::${articleAKey}::${articleBKey}`
}

export function isComparisonAlreadySaved({ historyItems, articleA, articleB, focus }) {
  const currentKey = getComparisonHistoryKey({ articleA, articleB, focus })

  if (!currentKey) {
    return false
  }

  return historyItems.some((item) => {
    const itemFocus = item.focus ?? item.comparison?.focus ?? 'general'
    return getComparisonHistoryKey({ articles: item.articles, focus: itemFocus }) === currentKey
  })
}

export function dedupeHistoryItems(historyItems) {
  const seen = new Set()

  return historyItems.filter((item) => {
    const itemFocus = item.focus ?? item.comparison?.focus ?? 'general'
    const key = getComparisonHistoryKey({ articles: item.articles, focus: itemFocus })

    if (!key) {
      return true
    }

    if (seen.has(key)) {
      return false
    }

    seen.add(key)
    return true
  })
}
