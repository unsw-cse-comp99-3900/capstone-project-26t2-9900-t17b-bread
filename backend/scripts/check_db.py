"""Verify PostgreSQL connectivity and optionally apply init_db.sql.

Run from the backend directory:
    python scripts/check_db.py
    python scripts/check_db.py --init
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
INIT_SQL = ROOT / "database" / "database" / "init_db.sql"


def load_database_url() -> str:
    """Read DATABASE_URL via the same Settings loader the app uses."""
    # Import here so the script works when invoked as `python scripts/check_db.py`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.config import get_settings

    url = get_settings().database_url.strip()
    if not url:
        raise ValueError(
            "DATABASE_URL is empty. Copy backend/.env.example to backend/.env "
            "and set your PostgreSQL credentials."
        )
    return url


def to_psycopg_url(url: str) -> str:
    """Strip SQLAlchemy driver suffixes for direct psycopg connections."""
    return (
        url.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
    )


def run_sql_file(cur, sql_path: Path) -> None:
    """Execute a multi-statement SQL file statement by statement."""
    lines = sql_path.read_text(encoding="utf-8").splitlines()
    sql = "\n".join(
        line for line in lines if not line.strip().startswith("--")
    )
    for chunk in sql.split(";"):
        statement = chunk.strip()
        if statement:
            cur.execute(statement)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check PostgreSQL connection.")
    parser.add_argument(
        "--init",
        action="store_true",
        help="Apply database/database/init_db.sql when required tables are missing.",
    )
    args = parser.parse_args()

    try:
        conn = psycopg.connect(to_psycopg_url(load_database_url()), connect_timeout=5)
    except Exception as exc:
        print("CONNECTION_FAIL:", type(exc).__name__, str(exc))
        print("\nNext steps:")
        print("  1. Set DATABASE_URL in backend/.env (see .env.example)")
        print("  2. Ensure PostgreSQL is running and init_db.sql has been applied")
        print("  3. Restart uvicorn after editing .env")
        return 1

    print("CONNECTION_OK")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"
        )
        tables = [row[0] for row in cur.fetchall()]
        print("tables:", tables or "(none)")

        needed = {"articles", "paragraph_chunks", "embeddings", "comparison_results", "history"}
        missing = needed - set(tables)
        if missing and args.init:
            if not INIT_SQL.exists():
                print("init script not found:", INIT_SQL)
                return 1
            run_sql_file(cur, INIT_SQL)
            conn.commit()
            print("applied init_db.sql")
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"
            )
            tables = [row[0] for row in cur.fetchall()]
            print("tables now:", tables)
        elif missing:
            print("missing tables:", sorted(missing))
            print("run: python scripts/check_db.py --init")

        for name in ("articles", "paragraph_chunks", "embeddings", "comparison_results", "history"):
            if name in tables:
                cur.execute(f"SELECT COUNT(*) FROM {name}")
                print(f"{name} rows:", cur.fetchone()[0])

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
