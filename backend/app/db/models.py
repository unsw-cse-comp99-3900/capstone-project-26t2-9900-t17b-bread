"""ORM models mirroring ``database/database/init_db.sql``.

These map onto tables created by the database team's init script. We do not
create or migrate the schema from the backend; the column definitions here are
kept in sync with that SQL file.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Article(Base):
    """``articles`` table — cleaned title, domain and main body text."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # NOTE: the SQL column is `main_body`; the API schema calls it `body_text`.
    main_body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class UserSession(Base):
    """``user_sessions`` table — session token + compared article URLs."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(String(255), nullable=False)
    article_a_url: Mapped[str] = mapped_column(Text, nullable=False)
    article_b_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
