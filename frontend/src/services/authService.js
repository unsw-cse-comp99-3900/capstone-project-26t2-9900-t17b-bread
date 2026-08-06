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

export function requestRegisterCode({ username, email }) {
  return fetch('/api/auth/register/request-code', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email }),
  }).then(parseJsonResponse)
}

export function verifyRegisterCode({
  username,
  email,
  password,
  verificationCode,
}) {
  return fetch('/api/auth/register/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      email,
      password,
      code: verificationCode,
    }),
  }).then(parseJsonResponse)
}

export function requestPasswordResetCode({ email }) {
  return fetch('/api/auth/password/request-reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  }).then(parseJsonResponse)
}

export function confirmPasswordReset({ email, verificationCode, newPassword }) {
  return fetch('/api/auth/password/confirm-reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      code: verificationCode,
      new_password: newPassword,
    }),
  }).then(parseJsonResponse)
}

export function logoutUser(authToken) {
  return fetch('/api/auth/logout', {
    method: 'POST',
    headers: authHeaders(authToken),
  })
}
