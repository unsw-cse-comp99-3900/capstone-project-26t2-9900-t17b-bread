# Backend Database Integration Guide

This document is for the **database developer** on the team. It explains how to connect your PostgreSQL instance to the FastAPI backend, which tables the backend expects, when data is written, and how to verify the integration.

The backend developer does **not** need a local database to run the API. Persistence is optional and controlled by a single environment variable.

---

## 1. Responsibilities

| Role | Owns |
|------|------|
| **Database developer** | PostgreSQL instance, `database/database/init_db.sql`, accounts/permissions, schema changes |
| **Backend developer** | `backend/` code, `backend/.env` connection settings, read/write logic in `app/db/` |

### Principles

1. **Schema source of truth:** `database/database/init_db.sql`
2. The backend **does not** create tables or run migrations. The database team runs the init script.
3. If `DATABASE_URL` is empty, the API runs normally but **does not persist** anything.

---

## 2. How the backend connects

The backend reads **`DATABASE_URL`** from `backend/.env` (this file is gitignored).

### Connection string format

```text
postgresql+psycopg://<user>:<password>@<host>:<port>/<database>
```

Example:

```text
postgresql+psycopg://postgres:your_password@localhost:5432/postgres
```

A plain URL also works (the backend adds the async driver automatically):

```text
postgresql://postgres:your_password@localhost:5432/postgres
```

### Setup (database developer machine)

```powershell
cd backend
copy .env.example .env
# Edit .env and set DATABASE_URL with your PostgreSQL credentials

pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Important:** After editing `.env`, **restart uvicorn**. Settings are cached at startup.

The backend loads `backend/.env` by absolute path, so uvicorn can be started from the repo root or from `backend/` — both work.

---

## 3. Required tables (Sprint 2)

The backend currently reads and writes **five tables**, defined in `database/database/init_db.sql`. The Sprint 1 `user_sessions` table no longer exists — `session_token` is generated in-memory per request and returned in the response, not persisted to its own table.

| Table | Purpose |
|-------|---------|
| `articles` | Cleaned article title, domain, and main body text |
| `paragraph_chunks` | One row per paragraph of an article |
| `embeddings` | One SBERT vector per paragraph chunk |
| `comparison_results` | Alignment matrix (`result_json`) + admin review state |
| `history` | Which `comparison_results` rows were saved/bookmarked |

### 3.1 `articles`

| Column | Type | Constraints | Written from |
|--------|------|-------------|--------------|
| `id` | SERIAL | PRIMARY KEY | auto-generated |
| `url` | TEXT | UNIQUE NOT NULL | `ProcessedArticle.url` |
| `title` | TEXT | nullable | `ProcessedArticle.title` |
| `source_domain` | VARCHAR(255) | nullable | `ProcessedArticle.source_domain` |
| `main_body` | TEXT | NOT NULL | paragraphs joined with `\n\n` |
| `created_at` | TIMESTAMP | DEFAULT now | server default |

**Field mapping note:** The API response uses `body_text` / `paragraphs`. The database column is **`main_body`**.

**Upsert behaviour:** If the same `url` is compared again, the row is updated (title, domain, body).

### 3.2 `paragraph_chunks`

| Column | Type | Constraints | Written from |
|--------|------|-------------|--------------|
| `id` | SERIAL | PRIMARY KEY | auto-generated |
| `article_id` | INT | FK → `articles.id`, ON DELETE CASCADE | the article this paragraph belongs to |
| `paragraph_index` | INT | NOT NULL | position of the paragraph in the article |
| `text_content` | TEXT | NOT NULL | paragraph text |
| `created_at` | TIMESTAMP | DEFAULT now | server default |

### 3.3 `embeddings`

| Column | Type | Constraints | Written from |
|--------|------|-------------|--------------|
| `id` | SERIAL | PRIMARY KEY | auto-generated |
| `chunk_id` | INT | FK → `paragraph_chunks.id`, ON DELETE CASCADE | the chunk this vector was computed from |
| `vector` | FLOAT8[] | NOT NULL | SBERT (`all-MiniLM-L6-v2`) embedding |
| `model_name` | TEXT | nullable | model used to compute the vector |
| `created_at` | TIMESTAMP | DEFAULT now | server default |

### 3.4 `comparison_results`

| Column | Type | Constraints | Written from |
|--------|------|-------------|--------------|
| `id` | SERIAL | PRIMARY KEY | auto-generated |
| `article_a_id` / `article_b_id` | INT | FK → `articles.id` | the compared article pair |
| `result_json` | JSONB | NOT NULL | frontend-facing match list + similarity score |
| `review_status` | VARCHAR(50) | DEFAULT `'pending'` | set by the admin review portal |
| `admin_notes` | TEXT | nullable | set by the admin review portal |
| `created_at` | TIMESTAMP | DEFAULT now | server default |

### 3.5 `history`

| Column | Type | Constraints | Written from |
|--------|------|-------------|--------------|
| `id` | SERIAL | PRIMARY KEY | auto-generated |
| `comparison_id` | INT | FK → `comparison_results.id`, ON DELETE CASCADE | the saved comparison |
| `saved_at` | TIMESTAMP | DEFAULT now | server default |

---

## 4. When data is written

| Endpoint | Writes to DB? | Notes |
|----------|---------------|-------|
| `POST /api/fetch` | No | Preview only |
| `POST /api/compare`, `/api/compare/stream`, `/api/compare/files`, `/api/compare/files/stream` | Yes | When both articles are processed successfully |
| `GET /health` | No | App health only |
| `GET /health/db` | No (ping only) | Runs `SELECT 1` |

### Compare endpoint write flow

1. Backend fetches, processes and compares both articles (no database involved).
2. If both articles succeeded:
   - **UPSERT** each article into `articles` (keyed by `url`).
   - **INSERT** each paragraph into `paragraph_chunks`, and its SBERT vector into `embeddings`.
   - **INSERT** one row into `comparison_results` (alignment matches + similarity score) and one linked row into `history`.
   - **COMMIT** the transaction.
3. A `session_token` (UUID) is always generated and returned in the response, whether or not persistence succeeded. If the write fails (DB unreachable, article missing, etc.), the error is **logged only** and the token is returned prefixed with `fallback-` — the API still returns `200` with the processed articles (best-effort persistence).

Example response snippet:

```json
{
  "focus": "general",
  "articles": ["..."],
  "errors": [],
  "comparison": {"focus": "general", "summary": {"match_count": 3}, "matches": ["..."]},
  "session_token": "a1b2c3d4e5f6789..."
}
```

---

## 5. Backend code map

You normally **do not need to edit** these files. Keep `init_db.sql` in sync with `app/db/models.py` if the schema changes.

| Path | Role |
|------|------|
| `app/config.py` | Loads `DATABASE_URL` from `backend/.env` |
| `app/db/base.py` | Async engine, session factory, health ping (used by `/health/db` only) |
| `app/db/models.py` | SQLAlchemy ORM models (must match SQL schema) |
| `app/db/repositories.py` | `ArticleRepository` (unused ORM write path — see note below) |
| `app/db/dal.py` | Raw-SQL data access layer actually used by `compare.py` |
| `app/api/routes/compare.py` | Opens its own synchronous engine and calls `app/db/dal.py` after successful processing |
| `admin_server.py` | Separate FastAPI app (port 8001) backing the admin review UI; reads/writes `comparison_results` directly |
| `scripts/check_db.py` | Connection test + optional init script runner |

**Driver:** `psycopg` (v3) everywhere — both the async engine in `app/db/base.py` and the synchronous engine in `app/api/routes/compare.py` / `admin_server.py` normalize `DATABASE_URL` to `postgresql+psycopg://` before connecting, so `psycopg2` is never required. Legacy `postgresql+asyncpg://` URLs are converted automatically too.

**Note:** the actual read/write path used in production is the raw-SQL `app/db/dal.py`, called directly from `app/api/routes/compare.py`'s own synchronous engine — not the async ORM layer (`app/db/base.py` + `app/db/repositories.py` + `app/services/compare_helpers.py`). The ORM layer is currently dead code, kept only because `app/db/models.py` is the authoritative column-level mirror of `init_db.sql`.

---

## 6. Verification checklist

### Step 1 — Create tables

Run the init script in pgAdmin or psql (contents of `database/database/init_db.sql`).

Or, from the **`backend/`** directory:

```powershell
cd backend
python scripts\check_db.py --init
```

Expected output:

```text
CONNECTION_OK
tables: ['articles', 'comparison_results', 'embeddings', 'history', 'paragraph_chunks']
articles rows: 0
paragraph_chunks rows: 0
embeddings rows: 0
comparison_results rows: 0
history rows: 0
```

Empty tables are normal. Rows appear only after someone calls `POST /api/compare`.

### Step 2 — Check backend connectivity

With uvicorn running, open:

<http://localhost:8000/health/db>

| Response | Meaning |
|----------|---------|
| `{"database":"ok"}` | Connected |
| `{"database":"error"}` | Wrong credentials, PostgreSQL not running, or missing tables |
| `{"database":"disabled"}` | `DATABASE_URL` is empty in `.env` |

### Step 3 — Write test

1. Open <http://localhost:8000/docs>
2. Call `POST /api/compare` with two reachable news article URLs
3. Query the database:

```sql
SELECT id, url, title, source_domain, LEFT(main_body, 80) AS preview
FROM articles
ORDER BY id DESC
LIMIT 5;

SELECT id, article_a_id, article_b_id, review_status, admin_notes, created_at
FROM comparison_results
ORDER BY id DESC
LIMIT 5;
```

---

## 7. FAQ

**Why are tables empty after setup?**  
Only `POST /api/compare` writes data. `POST /api/fetch` does not.

**Can we change the schema?**  
Yes. Update together:

1. `database/database/init_db.sql`
2. `backend/app/db/models.py`
3. `backend/app/db/dal.py` (if write logic changes — this is the raw-SQL layer `compare.py`/`admin_server.py` actually use)

Then re-run integration checks.

**Backend logs show "Database health check failed"?**  
Check username, password, host, port, and database name in `backend/.env`. Restart uvicorn after changes.

---

## 8. Related documentation

| Document | Audience |
|----------|----------|
| [API.md](API.md) | Frontend — HTTP endpoints |
| [database/database/README.md](../database/database/README.md) | Database — init script overview |
| This file | Database ↔ backend integration |

---

## 9. Changelog

| Date | Notes |
|------|-------|
| 2026-06-25 | Initial Sprint 1 integration guide (articles + user_sessions) |
| 2026-07-26 | Sprint 2 refresh: `user_sessions` removed, `paragraph_chunks`/`embeddings`/`comparison_results`/`history` documented to match the current `init_db.sql`; `review_status`/`admin_notes` moved into `init_db.sql` instead of being patched in by `admin_server.py`; `compare.py`/`admin_server.py` now normalize `DATABASE_URL` the same way `app/db/base.py` does. |
