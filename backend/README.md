# Narrative Diff Backend

FastAPI backend for the T17B BREAD news narrative comparison tool.

The backend handles article ingestion, URL/text/file processing, paragraph-level
comparison, score generation, authentication, history persistence, and admin
review support.

## Structure

| Path | Purpose |
| ---- | ------- |
| `app/main.py` | FastAPI app setup, CORS, and route registration |
| `app/api/routes/` | API endpoints for fetch, compare, upload, auth, history, and debug |
| `app/services/` | Article processing, PDF/OCR handling, NLP comparison, scoring, and streaming helpers |
| `app/db/` | Database access functions and persistence models |
| `app/schemas/` | Pydantic request and response models |
| `scripts/` | Local database and smoke-test helpers |
| `tests/` | Backend unit and API tests |

## Dependencies

Runtime dependencies are listed in:

```powershell
requirements.txt
```

Development and CI tools are listed separately in:

```powershell
requirements-dev.txt
```

This keeps the Docker runtime image smaller because it does not install
test-only tools such as pytest, ruff, mypy, bandit, and pip-audit.

## Local Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
copy .env.example .env
```

Edit `.env` only if local configuration is required.

## Run Locally

```powershell
uvicorn app.main:app --reload
```

- API: <http://localhost:8000>
- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

## Tests

```powershell
python -m pytest tests/ -v
```

Some tests mock external services so they can run without live network access.

## Docker

The recommended full-system setup is from the repository root:

```powershell
docker compose -f docker/docker-compose.yml up --build
```

The backend and admin backend use the same Docker image. The admin backend only
changes the startup command, so the backend image does not need to be built
twice.

## Email Verification

Email verification supports two modes:

- Development mode: if `SMTP_HOST` is empty, the backend returns a local
  development verification code for testing.
- SMTP mode: if SMTP environment variables are configured, the backend sends
  the verification code through the configured email provider.

Real SMTP credentials should be provided through environment variables or a
local `.env` file and must not be committed to the repository.
