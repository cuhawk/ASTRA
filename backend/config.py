from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ASTRA_",
        extra="ignore",
    )

    db_path: str = "./astra.db"
    redis_url: str = "redis://localhost:6379/0"

    session_secret: str = Field(default="dev-only-not-for-prod-change-me-32-bytes")
    session_max_age_s: int = 60 * 60 * 24 * 14  # 14 days
    session_cookie_name: str = "astra_sid"
    session_cookie_secure: bool = False  # set True in prod

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://127.0.0.1:8000/auth/github/callback"

    vault_kek_hex: str = ""  # 64 hex chars = 32 bytes. Required at runtime.

    free_tier_daily_limit: int = 100

    base_url: str = "http://127.0.0.1:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
