# T17B BREAD News Narrative Comparison

COMP9900 capstone project for comparing how different news outlets report the same event.

The app lets users provide two article sources, sends them to the FastAPI backend, and displays cleaned article text with paragraph-level matched evidence, labels, explanations, filters, and progress feedback.

## Repository Layout

| Path | Description |
|------|-------------|
| `backend/` | FastAPI backend for fetching, uploads, OCR, preprocessing, NLP comparison, summary, and API responses |
| `backend/APIenglish.md` | Backend API reference for frontend integration |
| `backend/API中文.md` | Chinese backend API reference |
| `frontend/` | React + Vite frontend |
| `frontend/public/demo-files/` | Demo input pairs for URL, PDF, Word, and pasted text samples |
| `database/` | PostgreSQL schema and database notes |

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API: <http://localhost:8000>
- Swagger docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

Current backend support includes URL fetching, PDF/Word upload, scanned PDF OCR, PDF-to-Word export, pasted-text input, extractive summary generation, paragraph chunking, semantic matching, relationship classification, numbered match pairs, and streaming progress.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, usually:

```text
http://localhost:5173
```

The frontend calls backend routes through Vite's `/api` proxy to `http://localhost:8000`.

## Current Frontend Features

- Dummy logo and polished comparison UI
- Two article inputs with `URL`, `Paste text`, and `PDF / Word` modes
- Demo input buttons loaded from `frontend/public/demo-files/index.json`
- URL, PDF, Word, and text demo pairs
- Streaming progress bar for long backend processing
- Friendly validation and backend error messages
- OCR/PDF type helper UI and PDF-to-Word download support
- Desktop side-by-side article comparison
- Mobile Article A / Article B tabs
- Paragraph-level color-coded highlights using backend `a_paragraph_index` and `b_paragraph_index`
- Numbered match pairs using backend `pair_number`
- Hover/click one highlighted paragraph to strongly highlight the corresponding paragraph on the other side
- Relationship filters for aligned, partially aligned, and divergent matches
- Explanation panel with matched evidence previews
- Save results button that downloads the current comparison result as JSON

## Demo Inputs

Demo samples are grouped by folder under:

```text
frontend/public/demo-files/
```

Each demo pair has a `demo.json` file describing Article A and Article B. The frontend loads the list from:

```text
frontend/public/demo-files/index.json
```

Example structure:

```text
frontend/public/demo-files/
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

To add a new demo pair, create a new folder, add the pair files and `demo.json`, then add the `demo.json` path to `index.json`.

## Validation

Frontend checks:

```powershell
cd frontend
npm run lint
npm run build
```
