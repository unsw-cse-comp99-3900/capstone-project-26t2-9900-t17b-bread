# capstone-project-26t2-9900-t17b-bread

COMP9900 capstone project — **Comparison of Diverging Narratives in News Articles** (T17B BREAD).

A browser-based tool that compares two news articles about the same topic and highlights how different outlets frame the story.

## Repository layout

| Path | Description |
|------|-------------|
| `backend/` | FastAPI backend — article fetch, cleaning, preprocessing, comparison API |
| `backend/API.md` | **Frontend integration guide** (endpoints, request/response schemas, examples) |

## Backend (Sprint 1)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### API overview

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/api/fetch` | Fetch and clean a single article |
| `POST` | `/api/compare` | Process two articles for side-by-side display |

For full request/response formats, error handling, and frontend examples, see **[backend/API.md](backend/API.md)**.

## Frontend integration

Frontend developers should read `backend/API.md` before wiring up URL submission and the side-by-side article viewer. The main endpoint is `POST /api/compare`; CORS is enabled for `http://localhost:3000` and `http://localhost:5173` by default.
