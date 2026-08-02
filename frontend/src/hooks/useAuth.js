import { useEffect, useState } from 'react'
import {
  fetchCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
} from '../services/authService'
import { fetchHistory } from '../services/historyService'
import { normalizeHistoryItem } from '../utils/article'
import {
  isValidUsername,
  loadAuthSession,
  saveAuthSession,
} from '../utils/auth'
import { dedupeHistoryItems } from '../utils/history'

export function useAuth({
  onHistoryItemsChange,
  onWorkspaceReset,
  onHistoryClose,
  onStatusMessage,
}) {
  const [authSession, setAuthSession] = useState(loadAuthSession)
  const [isAuthOpen, setIsAuthOpen] = useState(false)
  const [authMode, setAuthMode] = useState('login')
  const [authForm, setAuthForm] = useState({
    displayName: '',
    username: '',
    password: '',
  })
  const [authError, setAuthError] = useState('')
  const [isAuthSubmitting, setIsAuthSubmitting] = useState(false)

  const authToken = authSession?.accessToken ?? ''
  const currentUser = authSession?.user ?? null

  async function refreshAccountHistory(token = authToken) {
    if (!token) {
      onHistoryItemsChange([])
      return
    }

    const payload = await fetchHistory(token)
    onHistoryItemsChange(
      dedupeHistoryItems((payload.items ?? []).map(normalizeHistoryItem)),
    )
  }

  useEffect(() => {
    let isActive = true

    async function loadAccountData() {
      if (!authToken) {
        onHistoryItemsChange([])
        return
      }

      try {
        const [mePayload, historyPayload] = await Promise.all([
          fetchCurrentUser(authToken),
          fetchHistory(authToken),
        ])

        if (!isActive) {
          return
        }

        const nextSession = { accessToken: authToken, user: mePayload }
        setAuthSession(nextSession)
        saveAuthSession(nextSession)
        onHistoryItemsChange(
          dedupeHistoryItems(
            (historyPayload.items ?? []).map(normalizeHistoryItem),
          ),
        )
      } catch {
        if (!isActive) {
          return
        }
        saveAuthSession(null)
        setAuthSession(null)
        onHistoryItemsChange([])
      }
    }

    loadAccountData()

    return () => {
      isActive = false
    }
  }, [authToken, onHistoryItemsChange])

  async function handleAuthSubmit(event) {
    event.preventDefault()
    setAuthError('')

    const username = authForm.username.trim()
    const password = authForm.password

    if (!username) {
      setAuthError('Enter a username.')
      return
    }

    if (!isValidUsername(username)) {
      setAuthError('Username must be 3-20 characters, letters/numbers/underscore only.')
      return
    }

    if (!password) {
      setAuthError('Enter your password.')
      return
    }

    if (authMode === 'register' && password.length < 6) {
      setAuthError('Use at least 6 characters for the password.')
      return
    }

    setIsAuthSubmitting(true)

    try {
      const payload =
        authMode === 'register'
          ? await registerUser({
              username,
              password,
              displayName: authForm.displayName.trim(),
            })
          : await loginUser({ username, password })

      const nextSession = {
        accessToken: payload.access_token,
        user: payload.user,
      }
      saveAuthSession(nextSession)
      setAuthSession(nextSession)
      setIsAuthOpen(false)
      setAuthForm({ displayName: '', username: '', password: '' })
      await refreshAccountHistory(payload.access_token)
      onStatusMessage(
        `Logged in as ${payload.user.display_name || payload.user.username}.`,
      )
    } catch (error) {
      setAuthError(error.message)
    } finally {
      setIsAuthSubmitting(false)
    }
  }

  async function handleLogout() {
    if (authToken) {
      await logoutUser(authToken).catch(() => {})
    }
    saveAuthSession(null)
    setAuthSession(null)
    onWorkspaceReset()
    onHistoryItemsChange([])
    onHistoryClose()
    onStatusMessage('Logged out.')
  }

  return {
    authToken,
    currentUser,
    isAuthOpen,
    setIsAuthOpen,
    authMode,
    setAuthMode,
    authForm,
    setAuthForm,
    authError,
    setAuthError,
    isAuthSubmitting,
    refreshAccountHistory,
    handleAuthSubmit,
    handleLogout,
  }
}
