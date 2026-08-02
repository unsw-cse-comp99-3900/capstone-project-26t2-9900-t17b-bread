export function AppHeader({
  backendStatus,
  currentUser,
  historyCount,
  isAboutOpen,
  onAboutClose,
  onAboutOpen,
  onHistoryToggle,
  onLoginOpen,
  onLogout,
}) {
  return (
    <>
      <header className="site-header">
        <a className="brand" href="/" aria-label="Narrative Diff home">
          <img
            className="brand-logo"
            src="/narrative-diff-icon.svg"
            alt=""
            aria-hidden="true"
          />
          <span>Narrative Diff</span>
        </a>
        <div className="header-actions">
          {currentUser ? (
            <>
              <button
                className="history-button"
                type="button"
                onClick={onHistoryToggle}
              >
                History
                {historyCount > 0 && <span>{historyCount}</span>}
              </button>
              <span className="user-pill">
                {currentUser.display_name || currentUser.username}
              </span>
              <button
                className="header-pill-button"
                type="button"
                onClick={onLogout}
              >
                Logout
              </button>
            </>
          ) : (
            <button
              className="header-pill-button"
              type="button"
              onClick={onLoginOpen}
            >
              Login
            </button>
          )}
          <button
            className="header-pill-button"
            type="button"
            onClick={onAboutOpen}
          >
            About
          </button>
          <span className="sprint-label">Sprint 3 prototype</span>
        </div>
      </header>

      <span
        className={`backend-status backend-status--${backendStatus}`}
        aria-label={`Backend ${backendStatus}`}
        title={`Backend ${backendStatus}`}
      />

      {isAboutOpen && (
        <div
          className="about-modal-backdrop"
          role="presentation"
          onMouseDown={onAboutClose}
        >
          <section
            className="about-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="about-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="about-modal__header">
              <div>
                <p className="eyebrow">About</p>
                <h2 id="about-title">Narrative Diff</h2>
              </div>
              <button
                className="about-modal__close"
                type="button"
                onClick={onAboutClose}
                aria-label="Close about dialog"
              >
                x
              </button>
            </div>
            <p>
              Narrative Diff compares two reports on the same event and shows
              where their paragraph-level evidence is similar, partially
              similar, or divergent.
            </p>
            <p>
              You can enter article URLs, paste text directly, or upload
              supported documents. The highlighted results include matched
              paragraph pairs, relationship labels, 0-20 scores, and
              explanations from the backend comparison pipeline.
            </p>
            <p>
              Logged-in users can save comparison history to the database and
              reopen previous results from the History panel.
            </p>
          </section>
        </div>
      )}
    </>
  )
}
