from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two folders above this file (app/core/config.py)
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All Configuration, Read from environment variables / The .env file."""
    app_name: str = "AI Employee OS API"
    # "development" exposes the debug block in 500 errors and enables /debug routes.
    # Set APP_ENV=production on any real server.
    app_env: str = "development"

    database_url: str

    # --- Authentication ---
    secret_key: str
    algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0)
    refresh_token_expire_days: int = Field(default=7, gt=0)
    # Bcrypt cost factor. 12 is a good default (about 250 ms per hash).
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)

    # Browser origins allowed to call the API (the frontend URLs).
    # To override in .env use JSON:  CORS_ORIGINS=["http://localhost:4200"]
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_strong(cls, value: str) -> str:
        """Fail fast at startup if the signing key is weak or still a placeholder."""
        if len(value) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return value

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "dev", "local"}


settings = Settings()