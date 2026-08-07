# Database Subsystem
This directory contains the database initialization script for **PostgreSQL 17**.

## Files
* **`init_db.sql`**: The SQL script to create tables, constraints, and indexes.
* **`README.md`**: This documentation file.

## Database Schema (Sprint 1 Baseline)
### 1. `articles` Table
* **Purpose**: Stores cleaned news titles, domains, and main body text.
* **Optimization**: The `url` field is set to `UNIQUE` to prevent duplicate indexing, with a B-Tree index for fast lookups.

Note: the Sprint 1 `user_sessions` table has been removed from `init_db.sql`. It is
no longer part of the schema; `session_token` is now only returned in the API
response, not persisted to its own table.

## Database Schema Updates
### 2. `users` Table
* **Purpose**: Stores login accounts with hashed passwords and optional display names.
* **Note**: `email` is optional (nullable), but a partial unique index (`idx_users_email_unique`) enforces uniqueness whenever it is set, to support email-based login/verification.

### 3. `auth_tokens` Table
* **Purpose**: Stores opaque bearer tokens issued after login. Tokens are linked to users and removed on logout.
* **Note**: `expires_at` marks when a token should stop being accepted; indexed for efficient expiry lookups/cleanup.

### 4. `email_verification_codes` Table
* **Purpose**: Stores short-lived, hashed verification codes used for email verification and password-reset flows (`purpose` distinguishes the two). `used_at` marks a code as consumed so it cannot be replayed.
* **Optimization**: Indexed on `(email, purpose, created_at DESC)` for fast "latest code for this email" lookups.

### 5. `paragraph_chunks` Table
* **Purpose**: Stores each article's paragraphs individually so they can be embedded and cross-mapped between article A and article B.
* **Optimization**: Indexed by `article_id` for fast per-article lookups; cascades on article delete.

### 6. `embeddings` Table
* **Purpose**: Stores one SBERT vector embedding per paragraph chunk to support NLP alignment.
* **Optimization**: Uses native PostgreSQL `FLOAT8[]` arrays to store embedding vectors efficiently; indexed by `chunk_id`.

### 7. `comparison_results` Table
* **Purpose**: Stores the cross-mapping alignment matrix (`result_json`), plus administrative review tracking (`review_status`, `admin_notes`) used by the admin review portal.
* **Optimization**: Uses the `JSONB` data type for flexible and high-performance storage of the alignment matrix. `review_status`/`admin_notes` are defined directly in `init_db.sql` (not patched in at runtime).

### 8. `history` Table
* **Purpose**: Records which `comparison_results` rows have been saved/bookmarked by each logged-in user, and when.

## Backend Connection Guide (FastAPI / SQLAlchemy)

Use the following connection string template in your local environment. Include
the `+psycopg` driver suffix — the backend's async engine upgrades a plain
`postgresql://` URL automatically, but the Sprint 2 comparison endpoint opens
its own synchronous engine and needs the explicit driver name to avoid
depending on the legacy `psycopg2` package:

```text
postgresql+psycopg://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/postgres
