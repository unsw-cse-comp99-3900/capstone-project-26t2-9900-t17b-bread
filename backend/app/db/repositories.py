"""Repositories — the Data Access Layer between services and the database.

Keeping persistence here (rather than in the route or pipeline) matches the
architecture diagram's Data Access Layer and keeps the pipeline pure/testable.
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Article, UserSession
from app.schemas.article import ProcessedArticle


class ArticleRepository:
    """Reads/writes for the ``articles`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_processed(self, article: ProcessedArticle) -> int:
        """Insert or update an article by URL, returning its row id.

        The cleaned main body is reconstructed by joining the article's
        paragraphs (the SQL ``main_body`` column).
        """
        main_body = "\n\n".join(article.paragraphs).strip()
        if not main_body:
            main_body = " ".join(s.text for s in article.sentences).strip()
        values = {
            "url": article.url,
            "title": article.title,
            "source_domain": article.source_domain,
            "main_body": main_body,
        }
        stmt = (
            pg_insert(Article)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["url"],
                set_={
                    "title": values["title"],
                    "source_domain": values["source_domain"],
                    "main_body": values["main_body"],
                },
            )
            .returning(Article.id)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())


class UserSessionRepository:
    """Writes for the ``user_sessions`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        session_token: str,
        article_a_url: str,
        article_b_url: str,
    ) -> int:
        """Record a comparison request, returning the new row id."""
        row = UserSession(
            session_token=session_token,
            article_a_url=article_a_url,
            article_b_url=article_b_url,
        )
        self.session.add(row)
        await self.session.flush()
        return int(row.id)
