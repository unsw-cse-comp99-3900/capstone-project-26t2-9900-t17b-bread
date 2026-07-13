"""Schemas describing article content as it flows through the pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.progress import ProcessingSummary


class FetchRequest(BaseModel):
    """Single-article fetch request used by the lightweight Fetch Controller."""

    url: str = Field(..., description="HTTP/HTTPS URL of the news article to fetch.")


class RawArticle(BaseModel):
    """Cleaned article content returned by the Fetch / Extraction stage (PROJ-2)."""

    url: str
    title: str | None = None
    source_domain: str | None = None
    body_text: str = ""
    source_type: str = Field(default="url", description='Either "url" or "upload".')

    @property
    def has_body(self) -> bool:
        return bool(self.body_text and self.body_text.strip())


class UploadResponse(BaseModel):
    """Response for a single uploaded PDF/Word document."""

    article: RawArticle
    processing: "ProcessingSummary"


class SentenceUnit(BaseModel):
    """A single prepared sentence (PROJ-4).

    Each sentence keeps a stable id and stays connected to its article source
    and position (AC 4.2), enabling later alignment and explanation steps.
    """

    id: str = Field(..., description='Stable id, e.g. "A-12".')
    article_ref: str = Field(..., description='Article this sentence belongs to, e.g. "A".')
    text: str
    paragraph_index: int = Field(..., description="0-based index of the source paragraph.")
    sentence_index: int = Field(..., description="0-based global sentence position in the article.")
    char_start: int = Field(..., description="Start offset within the cleaned body text.")
    char_end: int = Field(..., description="End offset within the cleaned body text.")


class ProcessedArticle(BaseModel):
    """Structured, comparison-ready representation of one article (PROJ-3 output)."""

    article_ref: str
    url: str
    title: str | None = None
    source_domain: str | None = None
    source_type: str = Field(default="url", description='Either "url" or "upload".')
    paragraphs: list[str] = Field(default_factory=list)
    sentences: list[SentenceUnit] = Field(default_factory=list)
    paragraph_chunks: list[dict] = Field(default_factory=list)


    summary: list[dict] = Field(
        default_factory=list,
        description=(
            "Extractive summary sentences selected directly from the article. "
            "Each item includes sentence text, source position, and relevance score."
        ),
    )