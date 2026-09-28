"""Application settings, loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
# The team keeps one shared .env at the repo root (WeatherGPT/.env); backend/.env, if present, wins.
ENV_FILES = (BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Database
    # Default matches the "db" service in the root docker-compose.yml. For a local run outside
    # Docker, set DATABASE_URL to use localhost instead of db.
    DATABASE_URL: str = "postgresql+asyncpg://weathergpt:weathergpt@db:5432/weathergpt"
    DB_CONNECT_TIMEOUT_SECONDS: float = Field(default=3.0, gt=0)

    # AI provider: only the key for the selected provider is needed.
    AI_PROVIDER: Literal["groq", "openai", "gemini", "none"] = "groq"
    # Also read from LLM_API_KEY, the name already used in the team's root .env.example.
    GROQ_API_KEY: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("GROQ_API_KEY", "LLM_API_KEY")
    )
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GEMINI_API_KEY: SecretStr | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OPENAI_API_KEY: SecretStr | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    AI_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)

    # External data providers (Open-Meteo is free and needs no key)
    WEATHER_API_BASE_URL: str = "https://api.open-meteo.com/v1"
    CLIMATE_API_BASE_URL: str = "https://archive-api.open-meteo.com/v1"
    GEOCODING_API_BASE_URL: str = "https://geocoding-api.open-meteo.com/v1"
    HTTP_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)

    # Official alert provider. "none" until an IMD/official feed is integrated.
    ALERT_PROVIDER: Literal["none"] = "none"

    # Cache TTLs (0 disables caching for that data type)
    CURRENT_WEATHER_TTL_SECONDS: int = Field(default=600, ge=0)
    FORECAST_TTL_SECONDS: int = Field(default=1800, ge=0)
    GEOCODING_TTL_SECONDS: int = Field(default=86400, ge=0)
    CLIMATE_TTL_SECONDS: int = Field(default=86400, ge=0)

    # Comma-separated list, e.g. "http://localhost:8081,https://app.example.com"
    CORS_ORIGINS: str = "*"

    # Optional shared key. When set, every /api/v1 request must send X-API-Key.
    API_KEY: SecretStr | None = None

    @field_validator("GROQ_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "API_KEY", mode="before")
    @classmethod
    def _empty_string_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def _use_async_driver(cls, value: str) -> str:
        # Hosted Postgres providers often hand out postgres:// URLs; SQLAlchemy async needs +asyncpg.
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://"):]
        if value.startswith("postgresql://"):
            value = "postgresql+asyncpg://" + value[len("postgresql://"):]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql+asyncpg://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
