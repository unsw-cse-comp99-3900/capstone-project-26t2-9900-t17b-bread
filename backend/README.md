# Narrative Diff — Backend (T17B BREAD)

FastAPI backend for the COMP9900 news narrative-comparison tool. This is the
**Sprint 1** foundation: article ingestion, content extraction/cleaning, and
sentence-level preprocessing, exposed through a single comparison endpoint.

## Architecture

The backend follows the service split from the proposal (p.19–20):

```
app/
├── main.py                      # FastAPI app + CORS + router wiring
├── config.py                    # Settings (.env)
├── api/routes/
│   ├── fetch.py                 # Fetch Controller  -> POST /api/fetch
│   └── compare.py               # Compare Controller -> POST /api/compare
├── schemas/                     # Pydantic request/response models
│   ├── article.py               # RawArticle, SentenceUnit, ProcessedArticle
│   └── compare.py               # CompareRequest/Response, ComparisonFocus
└── services/
    ├── validation.py            # URL validation (PROJ-1)
    ├── fetch_service.py         # Article Fetch Service (PROJ-2)
    ├── preprocessing_service.py # Cleaning + sentence prep (PROJ-2 / PROJ-4)
    ├── sentence_splitter.py     # Deterministic sentence segmentation
    ├── pipeline.py              # Unified processing pipeline (PROJ-3)
    ├── errors.py                # Structured PipelineError + stages
    └── sprint2_stubs.py         # SBERT / BM25 / comparison / explanation (TODO)
```

### Sprint 1 user-story coverage

| Story  | Where |
| ------ | ----- |
| PROJ-1 | `services/validation.py` (http/https checks, reject before processing) |
| PROJ-2 | `services/fetch_service.py` (retrieve + extract title/domain/body, strip noise) |
| PROJ-3 | `services/pipeline.py` + `api/routes/compare.py` (single callable pipeline + endpoint, structured errors) |
| PROJ-4 | `services/preprocessing_service.py` (sentence units with stable id, source ref, position; reproducible) |

## Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
copy .env.example .env             # then edit if needed
```

## Run

```powershell
uvicorn app.main:app --reload
```

- API: <http://localhost:8000>
- Interactive docs (Swagger): <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

## Endpoints

### `POST /api/fetch` — Fetch Controller (lightweight preview)

```json
{ "url": "https://www.example.com/news/story" }
```

Returns the cleaned `title`, `source_domain` and `body_text`.

### `POST /api/compare` — Compare Controller (Sprint 1)

```json
{
  "article_a_url": "https://outlet-a.com/story",
  "article_b_url": "https://outlet-b.com/story",
  "focus": "general"
}
```

Returns both articles processed into `paragraphs` + `sentences` (each sentence
keeps its `id`, `article_ref`, `paragraph_index`, `sentence_index` and char
offsets). Per-article failures appear under `errors` with the failing `stage`.
The `comparison` field is reserved for Sprint 2 output.

## Tests

```powershell
pytest
```

Tests cover URL validation, sentence segmentation, the preprocessing pipeline
(positions, noise filtering, reproducibility), and the HTTP endpoints
(mocked network). They run offline — no live network access required.

## Sprint 2 (next)

`services/sprint2_stubs.py` defines the contracts for the comparison half:
extractive summary → SBERT embeddings → BM25+cosine retrieval → crossmapping →
focus-based scaling/scoring → narrative comparison → rule-based explanations.
ML dependencies live in `requirements-ml.txt`.
