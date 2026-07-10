# Narrative Diff Frontend

React + Vite frontend for the T17B BREAD news narrative comparison tool. The UI supports URL or PDF/Word article inputs, streaming progress, side-by-side desktop reading, mobile article tabs, highlighted comparison evidence, filters, and explanations.

## Requirements

- Node.js LTS
- npm
- A running FastAPI backend for live article fetching
- Modern browser such as Chrome, Edge, Firefox or Safari

Check Node and npm are available:

```powershell
node --version
npm --version
```

Install frontend dependencies once before running the app:

```powershell
npm install
```

## Run locally

From this `frontend` directory:

```powershell
npm run dev
```

Open the local Vite URL shown in the terminal, usually:

```text
http://localhost:5173
```

## Backend connection

The frontend calls the backend with relative API paths:

```text
/api/compare/stream
/api/compare/files/stream
```

During local development, Vite proxies `/api` requests to the FastAPI backend:

```text
http://localhost:8000
```

Start the backend from the project `backend` directory:

```powershell
uvicorn app.main:app --reload
```

## Current features

- Two article inputs with URL or PDF/Word upload mode
- URL format validation
- PDF/Word file validation
- Comparison focus selector
- Live backend API integration through streaming compare endpoints
- Progress bar for long-running article processing
- Side-by-side cleaned article display on desktop
- Mobile Article A / Article B tab view on narrow screens
- Per-article backend error display
- User-friendly error messages for invalid links, blocked sites, paywalls, login-required pages, and upload problems
- Colour-coded comparison highlights for aligned, partially aligned, and divergent matches
- Highlight legend and relationship filters
- Click-to-inspect explanation panel for matched evidence
- Prepared Al Jazeera / ABC demo URLs
- Offline demo copy fallback when the demo URLs are used and the backend is unavailable

## Not implemented yet

- Backend-generated semantic sentence alignment
- Backend-generated comparison explanations
- Summary generation
- Database-backed comparison history
