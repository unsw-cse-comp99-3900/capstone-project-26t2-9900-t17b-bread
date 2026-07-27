# T17B BREAD News Narrative Comparison

COMP9900 capstone project for comparing how different news outlets report the same event.

The app accepts two article sources, sends them to the FastAPI backend, and displays paragraph-level comparison evidence in the React frontend.

## Repository Layout

| Path | Description |
|------|-------------|
| `backend/` | FastAPI backend and NLP comparison pipeline |
| `frontend/` | React + Vite frontend |
| `frontend/public/demo-files/` | Demo input pairs |
| `database/` | PostgreSQL schema |
| `docker/` | Full-stack Docker setup |

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

Frontend details and test notes are in `frontend/README.md`.

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

GitHub Actions runs `.github/workflows/full-stack-quality.yml` for frontend tests/lint/build, backend pytest with PostgreSQL, database schema setup, and Docker Compose config/build.
