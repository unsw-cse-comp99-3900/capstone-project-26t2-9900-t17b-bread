# T17B BREAD News Narrative Comparison

COMP9900 capstone project for comparing how different news outlets report the
same event.

The system accepts two article sources, processes them through the backend, and
shows paragraph-level similarities, partial similarities, divergences, scores, and
explanations in the frontend.

## Repository Layout

| Path                 | Description                                      |
| -------------------- | ------------------------------------------------ |
| `frontend/`          | React + Vite user interface                      |
| `backend/`           | FastAPI backend and NLP comparison pipeline      |
| `database/`          | PostgreSQL schema and database notes             |
| `docker/`            | Dockerfiles and full-stack Compose setup         |
| `.github/workflows/` | Automated frontend, backend, and Docker checks   |

## Run With Docker

From the repository root:

```powershell
docker compose -f docker/docker-compose.yml up --build
```

Open:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000>
- Backend docs: <http://localhost:8000/docs>
- Admin page: <http://localhost:5173/admin.html>
- Admin backend: <http://localhost:8001>
- PostgreSQL: `localhost:5432`

Email verification supports both development mode and real SMTP delivery. By
default, SMTP variables are empty, so the backend returns a development
verification code that can be used for local testing. This lets assessors create
accounts without configuring an external email service.

For production-style email delivery, set SMTP variables before starting Docker.
Do not commit real SMTP credentials to GitHub.

```powershell
$env:SMTP_HOST="smtp-provider-host"
$env:SMTP_PORT="587"
$env:SMTP_USERNAME="smtp_username"
$env:SMTP_PASSWORD="smtp_password_or_api_key"
$env:SMTP_FROM="sender@example.com"
$env:SMTP_USE_TLS="true"
docker compose -f docker/docker-compose.yml up --build
```

In normal use, no source code changes are required. The backend reads the SMTP
settings from environment variables, and `docker/docker-compose.yml` forwards
those variables into the backend container:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_USE_TLS`

If these variables are empty, the system stays in development mode and returns a
local verification code for testing. If they are set, the backend sends the code
through the configured SMTP provider.

Only change source files if the email behaviour itself needs to be modified:

- `backend/app/config.py`: defines the SMTP environment variable names and
  default values.
- `backend/app/api/routes/auth.py`: contains the verification-code generation
  and email-sending logic.
- `docker/docker-compose.yml`: passes SMTP environment variables into Docker.
- `backend/.env.example`: documents the optional SMTP variables for local setup.

Docker starts:

- `frontend`: built React app served by Nginx
- `backend`: main FastAPI API
- `admin-backend`: admin review API, using the same backend image with a
  different start command
- `postgres`: PostgreSQL database
- `db-init`: one-shot schema/migration runner

`db-init` runs `database/database/init_db.sql` every startup, so existing Docker
volumes receive compatible schema updates.

Backend runtime dependencies are kept in `backend/requirements.txt`. Developer
and CI tools such as pytest, ruff, mypy, bandit, and pip-audit are kept in
`backend/requirements-dev.txt`, so Docker runtime images do not install test-only
tools.

The first Docker build can take around 8-10 minutes because it installs Python
and Node dependencies and prepares NLP model resources. After the first
successful build, start the stack without rebuilding unless dependencies
changed:

```powershell
docker compose -f docker/docker-compose.yml up
```

To fully reset local Docker data:

```powershell
docker compose -f docker/docker-compose.yml down -v
docker compose -f docker/docker-compose.yml up --build
```

## Run Frontend Locally

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The backend should be running on
<http://localhost:8000>.

More frontend details are in `frontend/README.md`.

The frontend source is organised into components, hooks, services, utilities,
and feature-specific styles so UI work can be updated without editing one large
application file.

Comparison scores, interpretations, score guides, and sorting options are
provided by the backend. When a user selects General comparison, the backend
chooses one global factor (political, sentiment, economic, or social) for the
complete article pair. The frontend shows that automatically selected factor
and applies its per-pair relevance scores consistently across the result.

## Validation

Frontend:

```powershell
cd frontend
npm test
npm run lint
npm run build
```

Backend/database:

```powershell
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt
python scripts/check_db.py --init
python -m pytest tests/ -v
```

Docker:

```powershell
docker compose -f docker/docker-compose.yml config
docker compose -f docker/docker-compose.yml build
```
