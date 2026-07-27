# T17B BREAD News Narrative Comparison

COMP9900 capstone project for comparing how different news outlets report the same event.

The app lets users provide two article sources, sends them to the FastAPI backend, and displays cleaned article text with paragraph-level matched evidence, labels, explanations, filters, and progress feedback.

## Repository Layout

| Path | Description |
|------|-------------|
| `backend/` | FastAPI backend for fetching, uploads, OCR, preprocessing, NLP comparison, summary, and API responses |
| `backend/APIenglish.md` | Backend API reference for frontend integration |
| `backend/API中文.md` | Chinese backend API reference |
| `backend/DATABASE_INTEGRATION.md` | Database integration guide (English) |
| `backend/DATABASE_INTEGRATION中文.md` | Database integration guide (Chinese) |
| `frontend/` | React + Vite frontend |
| `frontend/public/demo-files/` | Demo input pairs for URL, PDF, Word, and pasted text samples |
| `database/` | PostgreSQL schema and database notes |
| `.github/workflows/backend-ci.yml` | Backend CI/CD pipeline (lint, security, tests, build) |

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

### Backend Features

#### Article Ingestion

- **URL fetching** — fetch and extract article body from any news URL (with paywall detection)
- **PDF/Word upload** — extract text from `.pdf` and `.docx` documents
- **Scanned PDF OCR** — auto-detect image-based PDFs and extract text via Tesseract OCR
- **PDF-to-Word export** — convert scanned PDFs into downloadable `.docx` files
- **Pasted text input** — accept raw text directly for comparison

#### NLP Comparison Pipeline

- **Paragraph chunking** — split articles into meaningful paragraph-level chunks
- **Sentence splitting** — rule-based sentence segmentation with abbreviation handling
- **Semantic embedding** — SBERT (`all-MiniLM-L6-v2`) sentence-level embeddings
- **BM25 retrieval** — lexical similarity scoring for keyword matching
- **Cosine similarity** — embedding-based semantic similarity
- **Hybrid scoring** — combined semantic + lexical scoring
- **Cross-mapping** — optimal paragraph-chunk alignment between articles
- **Contradiction detection** — NLI model (`nli-deberta-v3-base`) for entailment/contradiction evidence
- **Relationship classification** — label each pair as `aligned`, `partially_aligned`, or `divergent`
- **Focus scaling** — adjust comparison weights based on user-selected focus (political, sentiment, economic, social)
- **Extractive summary** — generate per-article bullet-point summaries

#### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `GET` | `/health/db` | Database connectivity check |
| `POST` | `/api/fetch` | Fetch and clean a single URL article |
| `POST` | `/api/fetch/stream` | Same with live SSE progress |
| `POST` | `/api/upload` | Upload PDF/Word and extract body text (auto-OCR) |
| `POST` | `/api/upload/stream` | Same with live SSE progress |
| `POST` | `/api/upload/pdf-type` | Detect if a PDF is text-based or scanned |
| `POST` | `/api/upload/pdf-to-word` | OCR a scanned PDF and download as Word |
| `POST` | `/api/compare` | Compare two articles (URL/text) |
| `POST` | `/api/compare/stream` | Same with live SSE progress |
| `POST` | `/api/compare/files` | Compare with mixed URL/text/file inputs |
| `POST` | `/api/compare/files/stream` | Same with live SSE progress |
| `GET` | `/debug/info` | Runtime system info (debug mode) |
| `GET` | `/debug/logs` | Recent application logs (debug mode) |
| `GET` | `/debug/health/detailed` | Detailed health with memory/subsystems |

#### Monitoring & Observability

- **Structured logging** — configurable JSON or human-readable format via `LOG_FORMAT`
- **Request correlation ID** — unique `X-Request-ID` header on every response for tracing
- **Response timing** — `X-Process-Time` header showing server-side latency
- **In-memory log buffer** — last 500 log entries accessible via `/debug/logs`
- **Runtime diagnostics** — `/debug/info` shows uptime, Python version, config, dependency versions
- **Detailed health check** — `/debug/health/detailed` reports memory, database, and OCR status

#### CI/CD Pipeline

Automated on every push/PR to `main` (backend changes only):

| Job | Tool | Purpose |
|-----|------|---------|
| Lint | Ruff | Code style, import order, common bug patterns |
| Type Check | mypy | Static type analysis |
| Security | Bandit + pip-audit | Code security scan + dependency vulnerability audit |
| Tests | pytest + coverage | Unit tests with coverage report |
| Build | Python import check | Verify app starts and OpenAPI schema generates |

Run locally:

```powershell
cd backend
ruff check .                          # Lint
ruff format .                         # Auto-format
bandit -r app/ -c pyproject.toml      # Security scan
python -m pytest tests/ -v --cov=app  # Tests + coverage
```

#### Database (Optional)

- PostgreSQL via async SQLAlchemy + psycopg
- Persists articles, chunks, embeddings, comparison results, and history
- Controlled by `DATABASE_URL` in `.env`; API works without a database

---

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

Backend checks:

```powershell
cd backend
ruff check .
python -m pytest tests/ -v
```
