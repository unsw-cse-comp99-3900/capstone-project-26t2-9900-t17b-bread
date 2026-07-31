export function getArticleHistoryKey(article) {
  return String(article?.id ?? article?.url ?? article?.title ?? '').trim()
}

export function isComparisonAlreadySaved({ historyItems, articleA, articleB, focus }) {
  const articleAKey = getArticleHistoryKey(articleA)
  const articleBKey = getArticleHistoryKey(articleB)

  if (!articleAKey || !articleBKey) {
    return false
  }

  return historyItems.some((item) => {
    const savedArticleA = item.articles?.find(
      (article) => article.article_ref === 'A',
    )
    const savedArticleB = item.articles?.find(
      (article) => article.article_ref === 'B',
    )

    return (
      item.focus === focus &&
      getArticleHistoryKey(savedArticleA) === articleAKey &&
      getArticleHistoryKey(savedArticleB) === articleBKey
    )
  })
}
