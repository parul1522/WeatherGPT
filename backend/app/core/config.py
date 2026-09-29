from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend infrastructure settings.

    AI settings (GROQ_API_KEY, GROQ_MODEL, IMD_DISTRICT_IDS) are read by
    ``ai/config.py`` from the same ``.env`` file. ``extra="ignore"`` lets the
    shared .env hold those and the mobile EXPO_PUBLIC_* variables without
    pydantic rejecting them.
    """

    DATABASE_URL: str = "postgresql://weathergpt:weathergpt@db:5432/weathergpt"
    REDIS_URL: str = "redis://redis:6379/0"
    SECRET_KEY: str = "change-me"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
