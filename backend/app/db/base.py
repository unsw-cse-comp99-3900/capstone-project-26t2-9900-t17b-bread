"""Async SQLAlchemy engine, session factory and FastAPI dependency.

The engine is created lazily on first use and only when ``DATABASE_URL`` is
configured. This keeps the backend (and the test suite) fully runnable without
a PostgreSQL instance — persistence simply becomes a no-op.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _normalize_url(url: str) -> str:
    """Ensure the URL uses the async ``psycopg`` driver (Windows-friendly).

    The database team's template uses a plain ``postgresql://`` URL; SQLAlchemy
    needs ``postgresql+psycopg://`` for the async engine, so we upgrade it
    transparently. Legacy ``postgresql+asyncpg://`` URLs are also accepted.
    """
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url[len("postgresql+asyncpg://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


def is_db_enabled() -> bool:
    """True when a database URL is configured."""
    return bool(get_settings().database_url.strip())


def get_engine() -> AsyncEngine | None:
    """Return the shared async engine, creating it on first use.

    Returns ``None`` when the database is disabled.
    """
    global _engine, _sessionmaker
    if not is_db_enabled():
        return None
    if _engine is None:
        url = _normalize_url(get_settings().database_url.strip())
        _engine = create_async_engine(url, pool_pre_ping=True, future=True)
        _sessionmaker = async_sessionmaker(
            _engine, expire_on_commit=False, class_=AsyncSession
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession] | None:
    """Return the session factory, or ``None`` when the database is disabled."""
    if get_engine() is None:
        return None
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession | None]:
    """FastAPI dependency yielding a session, or ``None`` when DB is disabled.

    Callers must handle the ``None`` case (treat it as "persistence off").
    """
    maker = get_sessionmaker()
    if maker is None:
        yield None
        return
    async with maker() as session:
        yield session


async def ping_db() -> bool:
    """Run ``SELECT 1`` to verify connectivity. Raises if the DB is unreachable."""
    engine = get_engine()
    if engine is None:
        return False
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True


async def dispose_engine() -> None:
    """Dispose the engine on shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
