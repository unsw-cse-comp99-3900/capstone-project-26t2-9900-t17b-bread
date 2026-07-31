import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  clearHistory,
  deleteHistoryItem,
  fetchHistory,
  saveHistoryEntry,
} from './historyService'

function jsonResponse(data) {
  return {
    ok: true,
    json: vi.fn().mockResolvedValue(data),
  }
}

describe('historyService', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue(jsonResponse({ items: [] }))
  })

  it('fetches history with the bearer token', async () => {
    await fetchHistory('token-1')

    expect(global.fetch).toHaveBeenCalledWith('/api/history', {
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('saves a comparison id to account history', async () => {
    await saveHistoryEntry('token-1', 42)

    expect(global.fetch).toHaveBeenCalledWith('/api/history', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer token-1',
      },
      body: JSON.stringify({ comparison_id: 42 }),
    })
  })

  it('deletes one item or clears all history', async () => {
    await deleteHistoryItem('token-1', 9)
    await clearHistory('token-1')

    expect(global.fetch).toHaveBeenCalledWith('/api/history/9', {
      method: 'DELETE',
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(global.fetch).toHaveBeenCalledWith('/api/history', {
      method: 'DELETE',
      headers: { Authorization: 'Bearer token-1' },
    })
  })
})
