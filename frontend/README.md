# Narrative Diff Frontend

React + Vite frontend for the Narrative Diff news comparison tool.

The frontend compares two article sources and displays paragraph-level matches, labels, filters, evidence details, account history, and export controls.

## Requirements

- Node.js LTS
- npm
- FastAPI backend on `http://localhost:8000`
- Modern browser

## Run Locally

```powershell
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

Vite proxies `/api` and `/health` to the backend.

## Run With Docker

From the repository root:

```powershell
docker compose -f docker/docker-compose.yml up --build
```

Open:

```text
http://localhost:5173
```

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

## Features

- URL, pasted text, PDF, and Word input modes
- Demo pair selectors
- Streaming compare progress
- Friendly validation and backend error messages
- Paragraph-level highlights and evidence panel
- Basic login/register dialog
- Account history backed by the database for logged-in users
- Relationship filters, summary, HTML report export, and copy summary
- Desktop side-by-side layout and mobile Article A/B tabs

## Demo Inputs

Active demos are listed in:

```text
public/demo-files/index.json
```

Each pair lives in its own folder with a `demo.json`.

To add a demo pair:

1. Create a folder under `public/demo-files/`.
2. Add a `demo.json` file.
3. Add paired files if the sample is `upload` or `text`.
4. Add the `demo.json` path to `public/demo-files/index.json`.

## Validation

```powershell
npm test
npm run lint
npm run build
```

Automated tests use Vitest and React Testing Library. Backend requests are mocked so tests do not depend on live news sites or NLP model runtime.

Current coverage:

- Main comparison page rendering
- URL and pasted-text validation
- About dialog
- Demo pair loading
- Mocked comparison result display and paragraph highlights
- Evidence panel, relationship filters, copy summary, and HTML report export
- Mobile Article A/B tab state
- Login dialog and database-backed account history

## Continuous Integration

Workflow:

```text
.github/workflows/full-stack-quality.yml
```

It runs frontend tests/lint/build and Docker Compose config/build.

## Manual Test Checklist

- Run one URL, text, and Word demo.
- Check invalid URL error handling.
- Confirm progress, auto-scroll, highlights, filters, evidence panel, login/history, copy, and save.
- Check desktop and mobile layouts.
