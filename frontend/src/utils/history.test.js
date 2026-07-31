import { describe, expect, it } from 'vitest'
import { isComparisonAlreadySaved } from './history'

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
})
