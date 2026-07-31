import { parseJsonResponse } from '../utils/api'
import { authHeaders } from '../utils/auth'

export function fetchCurrentUser(authToken) {
  return fetch('/api/auth/me', {
    headers: authHeaders(authToken),
  }).then(parseJsonResponse)
}

export function loginUser({ username, password }) {
  return fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  }).then(parseJsonResponse)
}

export function registerUser({ username, password, displayName }) {
  return fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      password,
      display_name: displayName,
    }),
  }).then(parseJsonResponse)
}

export function logoutUser(authToken) {
  return fetch('/api/auth/logout', {
    method: 'POST',
    headers: authHeaders(authToken),
  })
}
