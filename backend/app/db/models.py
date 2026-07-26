"""ORM models mirroring ``database/database/init_db.sql``.

These map onto tables created by the database team's init script. We do not
create or migrate the schema from the backend; the column definitions here are
kept in sync with that SQL file.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func, Float, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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


class ParagraphChunk(Base):
    """``paragraph_chunks`` table — per-paragraph text for one article."""

    __tablename__ = "paragraph_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class Embedding(Base):
    """``embeddings`` table — SBERT vector for one paragraph chunk."""

    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("paragraph_chunks.id", ondelete="CASCADE"))
    vector: Mapped[list[float]] = mapped_column(ARRAY(Float), nullable=False)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class ComparisonResult(Base):
    """``comparison_results`` table — stores the cross-mapping alignment matrix."""

    __tablename__ = "comparison_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_a_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    article_b_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(50), server_default="pending", nullable=False
    )
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )


class History(Base):
    """``history`` table — saved/bookmarked comparison results."""

    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comparison_id: Mapped[int] = mapped_column(
        ForeignKey("comparison_results.id", ondelete="CASCADE")
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
