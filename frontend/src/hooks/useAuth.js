import { useEffect, useState } from 'react'
import {
  confirmPasswordReset,
  fetchCurrentUser,
  loginUser,
  logoutUser,
  requestPasswordResetCode,
  requestRegisterCode,
  verifyRegisterCode,
} from '../services/authService'
import { fetchHistory } from '../services/historyService'
import { normalizeHistoryItem } from '../utils/article'
import {
  isValidEmail,
  isValidPassword,
  isValidUsername,
  isValidVerificationCode,
  loadAuthSession,
  passwordRequirementMessage,
  saveAuthSession,
} from '../utils/auth'
import { dedupeHistoryItems } from '../utils/history'

function createEmptyAuthForm() {
  return {
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    verificationCode: '',
    newPassword: '',
    confirmNewPassword: '',
  }
}

function formatVerificationStatus(payload, fallbackMessage) {
  return payload?.message ?? fallbackMessage
}

const resendCooldownSeconds = 60

export function useAuth({
  onHistoryItemsChange,
  onWorkspaceReset,
  onHistoryClose,
  onStatusMessage,
}) {
  const [authSession, setAuthSession] = useState(loadAuthSession)
  const [isAuthOpen, setIsAuthOpen] = useState(false)
  const [authMode, setAuthMode] = useState('login')
  const [authForm, setAuthForm] = useState(createEmptyAuthForm)
  const [pendingVerificationEmail, setPendingVerificationEmail] = useState('')
  const [developmentVerificationCode, setDevelopmentVerificationCode] = useState('')
  const [authError, setAuthError] = useState('')
  const [isAuthSubmitting, setIsAuthSubmitting] = useState(false)
  const [resendSecondsRemaining, setResendSecondsRemaining] = useState(0)

  const authToken = authSession?.accessToken ?? ''
  const currentUser = authSession?.user ?? null

  useEffect(() => {
    if (resendSecondsRemaining <= 0) {
      return undefined
    }

    const timerId = window.setTimeout(() => {
      setResendSecondsRemaining((seconds) => Math.max(0, seconds - 1))
    }, 1000)

    return () => window.clearTimeout(timerId)
  }, [resendSecondsRemaining])

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

    // Check the saved token on page load and remove it if the backend rejects it.
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
    const email = authForm.email.trim()
    const password = authForm.password
    const confirmPassword = authForm.confirmPassword
    const verificationCode = authForm.verificationCode.trim()
    const newPassword = authForm.newPassword
    const confirmNewPassword = authForm.confirmNewPassword

    if (authMode === 'forgot') {
      if (!email) {
        setAuthError('Enter your email address.')
        return
      }

      if (!isValidEmail(email)) {
        setAuthError('Enter a valid email address.')
        return
      }

      setIsAuthSubmitting(true)
      try {
        const payload = await requestPasswordResetCode({ email })
        setPendingVerificationEmail(email)
        setDevelopmentVerificationCode(payload.dev_code ?? '')
        setAuthMode('reset')
        setResendSecondsRemaining(resendCooldownSeconds)
        onStatusMessage(formatVerificationStatus(payload, 'Password reset code sent.'))
      } catch (error) {
        setAuthError(error.message)
      } finally {
        setIsAuthSubmitting(false)
      }
      return
    }

    if (authMode === 'reset') {
      if (!isValidVerificationCode(verificationCode)) {
        setAuthError('Enter the 6-digit verification code.')
        return
      }

      if (!isValidPassword(newPassword)) {
        setAuthError(passwordRequirementMessage)
        return
      }

      if (newPassword !== confirmNewPassword) {
        setAuthError('The new passwords do not match.')
        return
      }

      setIsAuthSubmitting(true)
      try {
        const payload = await confirmPasswordReset({
          email: pendingVerificationEmail,
          verificationCode,
          newPassword,
        })
        onStatusMessage(payload.message ?? 'Password has been reset.')
        setAuthMode('login')
        setPendingVerificationEmail('')
        setDevelopmentVerificationCode('')
        setAuthForm(createEmptyAuthForm())
      } catch (error) {
        setAuthError(error.message)
      } finally {
        setIsAuthSubmitting(false)
      }
      return
    }

    if (authMode === 'verify') {
      if (!isValidVerificationCode(verificationCode)) {
        setAuthError('Enter the 6-digit verification code.')
        return
      }

      setIsAuthSubmitting(true)
      try {
        const payload = await verifyRegisterCode({
          username,
          email: pendingVerificationEmail,
          password,
          verificationCode,
        })
        const nextSession = {
          accessToken: payload.access_token,
          user: payload.user,
        }
        saveAuthSession(nextSession)
        setAuthSession(nextSession)
        setIsAuthOpen(false)
        setAuthMode('login')
        setPendingVerificationEmail('')
        setDevelopmentVerificationCode('')
        setAuthForm(createEmptyAuthForm())
        await refreshAccountHistory(payload.access_token)
        onStatusMessage(`Logged in as ${payload.user.username}.`)
      } catch (error) {
        setAuthError(error.message)
      } finally {
        setIsAuthSubmitting(false)
      }
      return
    }

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

    if (authMode === 'register') {
      if (!email) {
        setAuthError('Enter your email address.')
        return
      }

      if (!isValidEmail(email)) {
        setAuthError('Enter a valid email address.')
        return
      }

      if (!isValidPassword(password)) {
        setAuthError(passwordRequirementMessage)
        return
      }

      if (password !== confirmPassword) {
        setAuthError('The passwords do not match.')
        return
      }

      setIsAuthSubmitting(true)
      try {
        const payload = await requestRegisterCode({ username, email })
        setPendingVerificationEmail(email)
        setDevelopmentVerificationCode(payload.dev_code ?? '')
        setAuthMode('verify')
        setResendSecondsRemaining(resendCooldownSeconds)
        onStatusMessage(formatVerificationStatus(payload, 'Verification code sent.'))
      } catch (error) {
        setAuthError(error.message)
      } finally {
        setIsAuthSubmitting(false)
      }
      return
    }

    setIsAuthSubmitting(true)

    try {
      const payload = await loginUser({ username, password })

      const nextSession = {
        accessToken: payload.access_token,
        user: payload.user,
      }
      saveAuthSession(nextSession)
      setAuthSession(nextSession)
      setIsAuthOpen(false)
      setAuthForm(createEmptyAuthForm())
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
    // Clear the workspace as well so the next user cannot see the previous result.
    saveAuthSession(null)
    setAuthSession(null)
    onWorkspaceReset()
    onHistoryItemsChange([])
    onHistoryClose()
    onStatusMessage('Logged out.')
  }

  async function handleResendCode() {
    if (resendSecondsRemaining > 0 || isAuthSubmitting) {
      return
    }

    setAuthError('')
    setIsAuthSubmitting(true)

    try {
      const email = pendingVerificationEmail || authForm.email.trim()
      const payload =
        authMode === 'verify'
          ? await requestRegisterCode({ username: authForm.username.trim(), email })
          : await requestPasswordResetCode({ email })

      setPendingVerificationEmail(email)
      setDevelopmentVerificationCode(payload.dev_code ?? '')
      setResendSecondsRemaining(resendCooldownSeconds)
      onStatusMessage(formatVerificationStatus(payload, 'Verification code sent.'))
    } catch (error) {
      setAuthError(error.message)
    } finally {
      setIsAuthSubmitting(false)
    }
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
    pendingVerificationEmail,
    setPendingVerificationEmail,
    developmentVerificationCode,
    setDevelopmentVerificationCode,
    resendSecondsRemaining,
    authError,
    setAuthError,
    isAuthSubmitting,
    refreshAccountHistory,
    handleAuthSubmit,
    handleLogout,
    handleResendCode,
  }
}
