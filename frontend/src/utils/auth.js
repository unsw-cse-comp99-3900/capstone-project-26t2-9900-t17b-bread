import { authSessionKey } from '../config/appConfig'

export function loadAuthSession() {
  try {
    const parsed = JSON.parse(localStorage.getItem(authSessionKey) ?? 'null')
    return parsed?.accessToken && parsed?.user ? parsed : null
  } catch {
    return null
  }
}

export function saveAuthSession(session) {
  if (!session) {
    localStorage.removeItem(authSessionKey)
    return
  }
  localStorage.setItem(authSessionKey, JSON.stringify(session))
}

export function authHeaders(authToken) {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {}
}

export function isValidUsername(value) {
  const username = value.trim()
  return /^[a-zA-Z0-9_]{3,20}$/.test(username)
}

