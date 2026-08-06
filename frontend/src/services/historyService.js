import { parseJsonResponse } from '../utils/api'
import { authHeaders } from '../utils/auth'

export function fetchHistory(authToken) {
  return fetch('/api/history', {
    headers: authHeaders(authToken),
  }).then(parseJsonResponse)
}

export function saveHistoryEntry(authToken, comparisonId) {
  return fetch('/api/history', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(authToken),
    },
    body: JSON.stringify({ comparison_id: comparisonId }),
  }).then(parseJsonResponse)
}

export function deleteHistoryItem(authToken, itemId) {
  return fetch(`/api/history/${itemId}`, {
    method: 'DELETE',
    headers: authHeaders(authToken),
  }).then(parseJsonResponse)
}

export function clearHistory(authToken) {
  return fetch('/api/history', {
    method: 'DELETE',
    headers: authHeaders(authToken),
  }).then(parseJsonResponse)
}
