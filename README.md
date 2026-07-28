# T17B BREAD News Narrative Comparison

COMP9900 capstone project for comparing how different news outlets report the same event.

The app accepts two article sources, sends them to the FastAPI backend, and displays paragraph-level comparison evidence in the React frontend.

## Repository Layout

| Path | Description |
|------|-------------|
| `backend/` | FastAPI backend for ingestion, upload parsing, OCR, NLP comparison, logging, and API responses |
| `backend/APIenglish.md` | Backend API reference |
| `backend/DATABASE_INTEGRATION.md` | Database integration guide |
| `frontend/` | React + Vite frontend |
| `frontend/public/demo-files/` | Demo input pairs |
| `database/` | PostgreSQL schema and database notes |
| `docker/` | Full-stack Docker setup |
| `.github/workflows/backend-ci.yml` | Backend quality workflow |
| `.github/workflows/full-stack-quality.yml` | Frontend and Docker build workflow |

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
- Database health: <http://localhost:8000/health/db>

The backend supports URL articles, pasted text, PDF/Word uploads, OCR for scanned PDFs, paragraph-level comparison, relationship labels, explanations, summaries, account login, and optional PostgreSQL persistence for saved history.

Debug routes are available in debug mode:

- `/debug/info`
- `/debug/logs`
- `/debug/health/detailed`

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

Frontend details, demo input notes, and test coverage are in `frontend/README.md`.

## Docker

From the repository root:

```powershell
docker compose -f docker/docker-compose.yml up --build
```

- Frontend: <http://localhost:5173>
- Backend: <http://localhost:8000>
- PostgreSQL: `localhost:5432`

Reset the database volume after schema changes:

```powershell
docker compose -f docker/docker-compose.yml down -v
docker compose -f docker/docker-compose.yml up --build
```

## Validation

Frontend checks:

```powershell
cd frontend
npm test
npm run lint
npm run build
```

Backend checks:

```powershell
cd backend
python scripts/check_db.py --init
python -m pytest tests/ -v
```

GitHub Actions currently covers frontend tests/lint/build, Docker Compose config/build, and the backend quality workflow from `main`.
