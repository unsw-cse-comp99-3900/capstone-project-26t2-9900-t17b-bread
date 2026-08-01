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
  error,
  isSubmitting,
  onClose,
  onModeChange,
  onFormChange,
  onSubmit,
}) {
  if (!isOpen) {
    return null
  }

  const isRegister = mode === 'register'

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
            <h2 id="auth-title">{isRegister ? 'Create account' : 'Log in'}</h2>
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
          {isRegister && (
            <label>
              Display name
              <input
                value={authForm.displayName}
                onChange={(event) =>
                  onFormChange({ ...authForm, displayName: event.target.value })
                }
                placeholder="Optional display name"
              />
            </label>
          )}
          <label>
            Username
            <input
              type="text"
              value={authForm.username}
              onChange={(event) =>
                onFormChange({ ...authForm, username: event.target.value })
              }
              placeholder="Enter a UserName"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={authForm.password}
              onChange={(event) =>
                onFormChange({ ...authForm, password: event.target.value })
              }
              placeholder={isRegister ? 'At least 6 characters' : 'Password'}
            />
          </label>

          {error && <p className="auth-error">{error}</p>}

          <button className="compare-button auth-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Please wait...' : isRegister ? 'Create account' : 'Log in'}
          </button>
        </form>

        <button
          className="auth-switch"
          type="button"
          onClick={() => onModeChange(isRegister ? 'login' : 'register')}
        >
          {isRegister
            ? 'Already have an account? Log in'
            : 'New here? Create an account'}
        </button>
      </section>
    </div>
  )
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
