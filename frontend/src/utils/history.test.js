import { describe, expect, it } from 'vitest'
import { dedupeHistoryItems, isComparisonAlreadySaved } from './history'

const articleA = {
  id: 1,
  article_ref: 'A',
  title: 'Article A',
  url: 'https://example.com/a',
}

const articleB = {
  id: 2,
  article_ref: 'B',
  title: 'Article B',
  url: 'https://example.com/b',
}

describe('history utilities', () => {
  it('detects an already saved article pair with the same focus', () => {
    expect(
      isComparisonAlreadySaved({
        historyItems: [
          {
            focus: 'general',
            articles: [articleA, articleB],
          },
        ],
        articleA,
        articleB,
        focus: 'general',
      }),
    ).toBe(true)
  })

  it('allows the same article pair when the focus changes', () => {
    expect(
      isComparisonAlreadySaved({
        historyItems: [
          {
            focus: 'general',
            articles: [articleA, articleB],
          },
        ],
        articleA,
        articleB,
        focus: 'political',
      }),
    ).toBe(false)
  })

  it('detects duplicates when saved articles only have ordered article data', () => {
    expect(
      isComparisonAlreadySaved({
        historyItems: [
          {
            focus: 'general',
            articles: [
              { title: 'Article A', url: 'https://www.example.com/a/' },
              { title: 'Article B', url: 'https://example.com/b?utm=demo' },
            ],
          },
        ],
        articleA: { title: 'Article A', url: 'https://example.com/a' },
        articleB: { title: 'Article B', url: 'https://example.com/b' },
        focus: 'general',
      }),
    ).toBe(true)
  })

  it('hides older duplicate history entries with the same article pair and focus', () => {
    const items = dedupeHistoryItems([
      {
        id: 'latest',
        focus: 'general',
        articles: [articleA, articleB],
      },
      {
        id: 'older',
        focus: 'general',
        articles: [
          { ...articleA, id: 9 },
          { ...articleB, id: 10 },
        ],
      },
      {
        id: 'different-focus',
        focus: 'political',
        articles: [articleA, articleB],
      },
    ])

    expect(items.map((item) => item.id)).toEqual([
      'latest',
      'different-focus',
    ])
  })
})
