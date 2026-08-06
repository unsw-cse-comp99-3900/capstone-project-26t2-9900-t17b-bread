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

export function isValidEmail(value) {
  const email = value.trim()
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

export function isValidVerificationCode(value) {
  return /^\d{6}$/.test(value.trim())
}

export function isValidPassword(value) {
  return value.length >= 8 && /[a-zA-Z]/.test(value) && /\d/.test(value)
}

export const passwordRequirementMessage =
  'Use at least 8 characters with at least one letter and one number.'

