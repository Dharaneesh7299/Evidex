"""Centralized application configuration loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the Evidex backend."""

    model_config = SettingsConfigDict(
        env_file=[
            str(BACKEND_ROOT.parent / ".env"),
            str(BACKEND_ROOT / ".env"),
        ],
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.8-flash", alias="GEMINI_MODEL")

    database_url: str = Field(
        default=f"sqlite:///{BACKEND_ROOT / ('evidex.db' if (BACKEND_ROOT / 'evidex.db').exists() or not (BACKEND_ROOT / 'paperproof.db').exists() else 'paperproof.db')}",
        alias="DATABASE_URL",
    )
    upload_dir: Path = Field(
        default=BACKEND_ROOT / "uploads",
        alias="UPLOAD_DIR",
    )

    cors_origins: Any = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        alias="CORS_ORIGINS",
    )
    max_upload_bytes: int = Field(default=26_214_400, alias="MAX_UPLOAD_BYTES")
    log_level: str = Field(default="info", alias="LOG_LEVEL")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value):  # type: ignore[override]
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    import json
                    return json.loads(value)
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("upload_dir", mode="before")
    @classmethod
    def _expand_path(cls, value):  # type: ignore[override]
        if isinstance(value, str) and value:
            expanded = Path(value).expanduser()
            if not expanded.is_absolute():
                expanded = (BACKEND_ROOT / expanded).resolve()
            return expanded
        return value

    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key) and self.gemini_api_key != "your_api_key_here"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings


# Convenience export for type checkers.
settings = get_settings()
