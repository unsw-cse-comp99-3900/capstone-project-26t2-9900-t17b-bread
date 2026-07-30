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

## Source Structure

```text
src/
  App.jsx
  App.css
  App.test.jsx
  config/appConfig.js
  utils/appHelpers.js
  test/
```

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
