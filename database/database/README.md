# Database Subsystem (Sprint 1)
This directory contains the database initialization script for **PostgreSQL 17**.

## Files
* **`init_db.sql`**: The SQL script to create tables, constraints, and indexes.
* **`README.md`**: This documentation file.

## Database Schema
### 1. `articles` Table
* **Purpose**: Stores cleaned news titles, domains, and main body text.
* **Optimization**: The `url` field is set to `UNIQUE` to prevent duplicate indexing, with a B-Tree index for fast lookups.

### 2. `user_sessions` Table
* **Purpose**: Stores user session tokens and the history of compared article URLs.
* **Optimization**: Indexed by `session_token` to quickly fetch history for the frontend.

## Backend Connection Guide (FastAPI / SQLAlchemy)

Use the following connection string template in your local environment:

```text
postgresql://postgres:YOUR_LOCAL_PASSWORD@localhost:5432/postgres
