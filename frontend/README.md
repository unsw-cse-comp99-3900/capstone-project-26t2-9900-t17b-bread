# Narrative Diff Frontend

React + Vite frontend for the T17B BREAD news narrative comparison tool.

The frontend supports URL, pasted text, PDF, and Word inputs, then displays paragraph-level comparison results from the backend with numbered highlights, explanations, filters, and save/export support.

## Requirements

- Node.js LTS
- npm
- FastAPI backend running on `http://localhost:8000`
- Modern browser such as Chrome, Edge, Firefox, or Safari

## Install

```powershell
npm install
```

## Run Locally

From this `frontend` directory:

```powershell
npm run dev
```

Open the Vite URL shown in the terminal, usually:

```text
http://localhost:5173
```

## Backend Connection

The app uses relative API paths:

```text
/api/compare/stream
/api/compare/files/stream
/api/upload/pdf-type
/api/upload/pdf-to-word
```

Vite proxies `/api` requests to:

```text
http://localhost:8000
```

Start the backend from the project `backend` directory:

```powershell
uvicorn app.main:app --reload
```

## Current Features

- Dummy logo and comparison-focused UI
- Two article inputs with `URL`, `Paste text`, and `PDF / Word` modes
- URL and text validation
- PDF/Word file validation
- PDF type detection for text PDFs versus scanned/image PDFs
- PDF-to-Word download helper
- Comparison focus selector
- Streaming compare requests with progress bar
- Desktop side-by-side article view
- Mobile Article A / Article B tabs
- User-friendly errors for invalid links, blocked sites, paywalls, login-required pages, upload failures, and OCR failures
- Paragraph-level color-coded highlights for `aligned`, `partially_aligned`, and `divergent`
- Numbered match pairs from backend `pair_number`
- Hover or click one highlighted paragraph to strongly highlight the paired paragraph on the other side
- Highlight legend and relationship filters
- Explanation panel with score, pair number, label, explanation, and matched evidence previews
- Save results button that downloads the current result as JSON

## Demo Inputs

Demo buttons are generated from:

```text
public/demo-files/index.json
```

Each demo pair lives in its own folder with a `demo.json` file. The pair is fixed by the `articleA` and `articleB` entries inside that folder's metadata.

Current structure:

```text
public/demo-files/
  index.json
  climate-pdf/
    1a.pdf
    1b.pdf
    demo.json
  gene-therapy-word/
    1a.docx
    1b.docx
    demo.json
  volcano-text/
    1a.txt
    1b.txt
    demo.json
  volcano-url/
    demo.json
```

To add a demo pair:

1. Create a new folder under `public/demo-files/`.
2. Add paired files inside that folder, usually named `1a` and `1b` with the correct file extension.
3. Add a `demo.json` describing the pair.
4. Add the `demo.json` path to `public/demo-files/index.json`.

Example `demo.json` for an uploaded PDF pair:

```json
{
  "id": "example-pdf",
  "label": "PDF",
  "description": "Example PDF article pair",
  "kind": "upload",
  "focus": "general",
  "articleA": {
    "filePath": "/demo-files/example-pdf/1a.pdf",
    "fileName": "1a.pdf",
    "mimeType": "application/pdf"
  },
  "articleB": {
    "filePath": "/demo-files/example-pdf/1b.pdf",
    "fileName": "1b.pdf",
    "mimeType": "application/pdf"
  }
}
```

## Validation

```powershell
npm run lint
npm run build
```
