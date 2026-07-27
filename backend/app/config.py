"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load backend/.env regardless of the shell's current working directory.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Logging & debug
    log_level: str = "INFO"
    log_format: str = "human"  # "human" or "json"
    debug_enabled: bool = False

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Article fetching
    fetch_timeout_seconds: float = 15.0
    fetch_max_bytes: int = 5_000_000
    fetch_user_agent: str = (
        "Mozilla/5.0 (compatible; NarrativeDiffBot/0.1; +https://example.edu)"
    )

    # Preprocessing
    # Sentences shorter than this many characters are treated as noise
    # (captions, bylines, "Share this", etc.) and skipped.
    min_sentence_chars: int = 15

    # Uploaded documents (PDF / Word)
    upload_max_bytes: int = 10_000_000

    # OCR for image-based (scanned) PDFs
    # A PDF is treated as image-based (scanned) when its directly extractable
    # text is below this many characters per page on average.
    pdf_image_char_threshold: int = 25
    # Rendering resolution for OCR; higher = more accurate but slower.
    ocr_dpi: int = 300
    # Tesseract language packs, e.g. "eng" or "eng+chi_sim".
    ocr_languages: str = "eng"
    # Optional absolute path to the tesseract executable (Windows convenience).
    # Leave empty to rely on PATH.
    tesseract_cmd: str = ""

    # Database (PostgreSQL). Leave empty to disable persistence entirely:
    # the API still works, it just won't store articles or sessions.
    # Accepts either "postgresql://" or "postgresql+psycopg://" — the async
    # driver is applied automatically (see app.db.base).
    database_url: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
