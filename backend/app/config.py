"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
