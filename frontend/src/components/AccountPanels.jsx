export function HistoryPanel({
  historyItems,
  isOpen,
  onClose,
  onRestore,
  onDelete,
  onClear,
}) {
  if (!isOpen) {
    return null
  }

  return (
    <section className="history-panel" aria-label="Comparison history">
      <div className="history-panel__header">
        <div>
          <p className="eyebrow">Account history</p>
          <h2>Saved comparisons</h2>
        </div>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>

      {historyItems.length > 0 ? (
        <>
          <div className="history-list">
            {historyItems.map((item) => (
              <div className="history-item" key={item.id}>
                <button type="button" onClick={() => onRestore(item)}>
                  <span>{item.label}</span>
                  <small>{item.description}</small>
                </button>
                <button
                  className="history-item__delete"
                  type="button"
                  onClick={() => onDelete(item.id)}
                  aria-label={`Delete ${item.label} from history`}
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
          <button className="history-clear-button" type="button" onClick={onClear}>
            Clear history
          </button>
        </>
      ) : (
        <p className="history-empty">
          Saved comparisons will appear here after a successful run.
        </p>
      )}
    </section>
  )
}

export function AuthModal({
  isOpen,
  mode,
  authForm,
  pendingVerificationEmail,
  developmentVerificationCode,
  resendSecondsRemaining,
  error,
  isSubmitting,
  onClose,
  onModeChange,
  onFormChange,
  onSubmit,
  onResendCode,
}) {
  if (!isOpen) {
    return null
  }

  const isRegister = mode === 'register'
  const isLogin = mode === 'login'
  const isVerify = mode === 'verify'
  const isForgot = mode === 'forgot'
  const isReset = mode === 'reset'
  const titleByMode = {
    login: 'Log in',
    register: 'Create account',
    verify: 'Verify email',
    forgot: 'Reset password',
    reset: 'Choose new password',
  }

  return (
    <div
      className="about-modal-backdrop"
      role="presentation"
      onMouseDown={onClose}
    >
      <section
        className="auth-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="about-modal__header">
          <div>
            <p className="eyebrow">Account</p>
            <h2 id="auth-title">{titleByMode[mode] ?? 'Account'}</h2>
          </div>
          <button
            className="about-modal__close"
            type="button"
            onClick={onClose}
            aria-label="Close login dialog"
          >
            x
          </button>
        </div>

        <form className="auth-form" onSubmit={onSubmit} noValidate>
          {(isLogin || isRegister) && (
            <label>
              Username
              <input
                type="text"
                value={authForm.username}
                onChange={(event) =>
                  onFormChange({ ...authForm, username: event.target.value })
                }
                placeholder="3-20 letters, numbers, or underscores"
              />
            </label>
          )}

          {(isRegister || isForgot) && (
            <label>
              Email
              <input
                type="email"
                value={authForm.email}
                onChange={(event) =>
                  onFormChange({ ...authForm, email: event.target.value })
                }
                placeholder="name@example.com"
              />
            </label>
          )}

          {(isLogin || isRegister) && (
            <label>
              Password
              <input
                type="password"
                value={authForm.password}
                onChange={(event) =>
                  onFormChange({ ...authForm, password: event.target.value })
                }
                placeholder={isRegister ? '8+ chars, letter and number' : 'Password'}
              />
            </label>
          )}

          {isRegister && (
            <label>
              Confirm password
              <input
                type="password"
                value={authForm.confirmPassword}
                onChange={(event) =>
                  onFormChange({ ...authForm, confirmPassword: event.target.value })
                }
                placeholder="Re-enter password"
              />
            </label>
          )}

          {isVerify && (
            <>
              <p className="auth-help">
                Enter the 6-digit code sent to {pendingVerificationEmail || 'your email'}.
              </p>
              {developmentVerificationCode && (
                <p className="auth-dev-code">
                  Development mode code: <strong>{developmentVerificationCode}</strong>
                </p>
              )}
              <label>
                Verification code
                <input
                  inputMode="numeric"
                  maxLength={6}
                  value={authForm.verificationCode}
                  onChange={(event) =>
                    onFormChange({ ...authForm, verificationCode: event.target.value })
                  }
                  placeholder="6-digit code"
                />
              </label>
              <ResendCodeButton
                secondsRemaining={resendSecondsRemaining}
                isSubmitting={isSubmitting}
                onResend={onResendCode}
              />
            </>
          )}

          {isReset && (
            <>
              <p className="auth-help">
                Enter the 6-digit code sent to {pendingVerificationEmail || 'your email'}.
              </p>
              {developmentVerificationCode && (
                <p className="auth-dev-code">
                  Development mode code: <strong>{developmentVerificationCode}</strong>
                </p>
              )}
              <label>
                Verification code
                <input
                  inputMode="numeric"
                  maxLength={6}
                  value={authForm.verificationCode}
                  onChange={(event) =>
                    onFormChange({ ...authForm, verificationCode: event.target.value })
                  }
                  placeholder="6-digit code"
                />
              </label>
              <ResendCodeButton
                secondsRemaining={resendSecondsRemaining}
                isSubmitting={isSubmitting}
                onResend={onResendCode}
              />
              <label>
                New password
                <input
                  type="password"
                  value={authForm.newPassword}
                  onChange={(event) =>
                    onFormChange({ ...authForm, newPassword: event.target.value })
                  }
                  placeholder="8+ chars, letter and number"
                />
              </label>
              <label>
                Confirm new password
                <input
                  type="password"
                  value={authForm.confirmNewPassword}
                  onChange={(event) =>
                    onFormChange({ ...authForm, confirmNewPassword: event.target.value })
                  }
                  placeholder="Re-enter new password"
                />
              </label>
            </>
          )}

          {error && <p className="auth-error">{error}</p>}

          <button className="compare-button auth-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Please wait...' : getAuthSubmitLabel(mode)}
          </button>
        </form>

        <div className="auth-switch-group">
          {isLogin && (
            <button
              className="auth-switch"
              type="button"
              onClick={() => onModeChange('forgot')}
            >
              Forgot password?
            </button>
          )}
          <button
            className="auth-switch"
            type="button"
            onClick={() => onModeChange(isRegister || isForgot || isReset || isVerify ? 'login' : 'register')}
          >
            {isRegister || isForgot || isReset || isVerify
              ? 'Back to login'
              : 'New here? Create an account'}
          </button>
        </div>
      </section>
    </div>
  )
}

function ResendCodeButton({ secondsRemaining = 0, isSubmitting, onResend }) {
  return (
    <button
      className="auth-switch auth-resend"
      type="button"
      disabled={isSubmitting || secondsRemaining > 0}
      onClick={onResend}
    >
      {secondsRemaining > 0
        ? `Resend code in ${secondsRemaining}s`
        : 'Resend code'}
    </button>
  )
}

function getAuthSubmitLabel(mode) {
  if (mode === 'register') {
    return 'Send verification code'
  }
  if (mode === 'verify') {
    return 'Verify account'
  }
  if (mode === 'forgot') {
    return 'Send reset code'
  }
  if (mode === 'reset') {
    return 'Reset password'
  }
  return 'Log in'
}

export function SaveOptionsModal({
  isOpen,
  currentUser,
  onClose,
  onDownloadHtml,
}) {
  if (!isOpen) {
    return null
  }

  return (
    <div
      className="about-modal-backdrop"
      role="presentation"
      onMouseDown={onClose}
    >
      <section
        className="save-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="save-options-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="about-modal__header">
          <div>
            <p className="eyebrow">Save result</p>
            <h2 id="save-options-title">Choose a local copy</h2>
          </div>
          <button
            className="about-modal__close"
            type="button"
            onClick={onClose}
            aria-label="Close save options"
          >
            x
          </button>
        </div>

        <p className="save-modal__copy">
          {currentUser
            ? 'This comparison is saved to your account history. You can also download a readable local report.'
            : 'Log in to save this comparison to account history, or download a readable local report.'}
        </p>

        <div className="save-modal__actions">
          <button className="compare-button" type="button" onClick={onDownloadHtml}>
            Download HTML report
          </button>
        </div>
      </section>
    </div>
  )
}
