"""Database layer (PostgreSQL via async SQLAlchemy).

This package is self-contained and optional: when ``DATABASE_URL`` is not set,
``is_db_enabled()`` returns False and the rest of the app skips persistence.
The ORM models here mirror the schema in ``database/database/init_db.sql`` —
that SQL script remains the source of truth for table creation; we do not
create or migrate tables from the backend.
"""
