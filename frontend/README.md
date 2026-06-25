# Narrative Diff Frontend

React + Vite frontend for the T17B BREAD news narrative comparison tool.

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

The frontend calls the backend with a relative API path:

```text
/api/compare
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

- Two article URL inputs
- URL format validation
- Comparison focus selector
- Live backend API integration
- Side-by-side cleaned article display
- Per-article backend error display
- Loading state while comparing
- Prepared Al Jazeera / ABC demo URLs
- Offline demo copy fallback when the demo URLs are used and the backend is unavailable

## Not implemented yet

- Semantic sentence alignment
- Colour-coded similarity/difference highlighting
- Explanation panel
- Summary generation
- Database-backed comparison history
