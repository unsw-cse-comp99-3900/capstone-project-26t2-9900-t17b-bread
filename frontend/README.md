# Narrative Diff Frontend

React + Vite frontend for the Narrative Diff news comparison tool.

The page lets users compare two reports, inspect paragraph-level evidence, save
results, and review account history when logged in.

## Run Locally

```powershell
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

The local Vite server proxies `/api` and `/health` to the backend at
`http://localhost:8000`.

## Run With Docker

From the repository root:

```powershell
docker compose -f docker/docker-compose.yml up --build
```

Open:

```text
http://localhost:5173
```

## Main Features

- URL, pasted text, PDF, and Word input modes
- Demo selectors for URL, Word, and text examples
- Streaming progress while comparison runs
- Friendly validation and backend error messages
- Paragraph-level colour highlights
- Side-by-side desktop article view and mobile Article A/B tabs
- Evidence panel with backend-provided 0-20 scores
- General comparison with one backend-selected global factor
- Per-pair relevance scores for the selected or automatically chosen factor
- Backend-driven sorting and relationship filters
- High-level summary card
- Basic login/register modal
- Database-backed account history for logged-in users
- Local HTML report export

## Demo Inputs

Active demos are listed in:

```text
public/demo-files/index.json
```

Each demo pair has its own folder and `demo.json`.

To add a demo:

1. Create a folder under `public/demo-files/`.
2. Add a `demo.json`.
3. Add paired files for text or upload demos.
4. Add the `demo.json` path to `public/demo-files/index.json`.

Selecting a demo fills the inputs only. It does not change the selected
comparison focus.

## Comparison Response

The frontend treats the backend comparison response as the source of truth. It
does not recalculate scores, score levels, interpretations, score ranges, or
sorting rules.

For General comparison, the backend evaluates political, sentiment, economic,
and social factors across both articles, then returns one factor in
`comparison.selected_factor`. The frontend displays it as the automatically
selected factor. Every item in `comparison.matches` may contain a different
`factor_relevance.score`, but all matches in that comparison use the same
factor.

The result UI uses:

- `comparison.matches` for paragraph pairs and per-pair scores
- `comparison.selected_factor` for the global factor
- `comparison.summary` for counts and average scores
- `comparison.score_guides` for titles, questions, score bands, and disclaimers
- `comparison.sorting.options` for available sorting controls and score paths

`selected_factor` and `factor_relevance` remain optional in the frontend so
older saved comparisons can still be opened.

## Source Structure

```text
src/
  App.jsx                         # page composition and state wiring
  main.jsx
  index.css                       # global variables and base browser styles
  components/                     # reusable UI sections
    AccountPanels.jsx
    AppHeader.jsx
    ArticleInputs.jsx
    ArticlePanel.jsx
    CompareInputSection.jsx
    ComparisonResults.jsx
    MatchExplanationPanel.jsx
  hooks/                          # frontend state and workflow logic
    useArticleInputs.js
    useAuth.js
    useBackendStatus.js
    useComparison.js
    useDemoSamples.js
    useResultActions.js
  services/                       # API calls
    authService.js
    compareService.js
    demoService.js
    healthService.js
    historyService.js
    uploadService.js
  styles/                         # feature-specific CSS
    index.css
    layout.css
    account.css
    inputs.css
    comparison.css
    explanation-panel.css
    utilities.css
    responsive.css
  utils/                          # formatting, validation, export helpers
  test/                           # shared test setup and mock data
  App.workflow.test.jsx
  App.comparison.test.jsx
  App.auth-history.test.jsx
```

`App.jsx` should stay focused on composing the page. New workflow logic should
normally go into hooks, API calls into services, formatting/validation into
utils, and visual changes into the relevant file under `styles/`.

## Validation

```powershell
npm test
npm run lint
npm run build
```

Tests use Vitest and React Testing Library. Backend requests are mocked so the
frontend tests do not depend on live news sites or NLP model runtime.

Current coverage includes:

- Rendering and form validation
- Demo loading
- Comparison result display
- Paragraph highlighting and evidence panel
- Backend-driven score display and sorting
- General-focus global factor display and factor-relevance score guides
- Compatibility with saved results from the previous response shape
- Relationship filters
- Login/logout and account history behaviour
- HTML report export
- Mobile tab state

## Manual Checks

- Run one URL demo, one text demo, and one Word demo.
- Try an invalid URL and confirm the message is readable.
- Confirm compare progress, auto-scroll, highlights, filters, sorting, and the
  evidence panel.
- Log in, save a result, reopen history, restore it, then log out.
- Check desktop and mobile layouts.
