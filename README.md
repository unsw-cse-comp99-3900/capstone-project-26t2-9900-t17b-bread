# T17B BREAD News Narrative Comparison

COMP9900 capstone project for comparing how different news outlets report the
same event.

The system accepts two article sources, processes them through the backend, and
shows paragraph-level similarities, partial alignments, divergences, scores, and
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

Docker starts:

- `frontend`: built React app served by Nginx
- `backend`: main FastAPI API
- `admin-backend`: admin review API
- `postgres`: PostgreSQL database
- `db-init`: one-shot schema/migration runner

`db-init` runs `database/database/init_db.sql` every startup, so existing Docker
volumes receive compatible schema updates.

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
python scripts/check_db.py --init
python -m pytest tests/ -v
```

Docker:

```powershell
docker compose -f docker/docker-compose.yml config
docker compose -f docker/docker-compose.yml build
```
