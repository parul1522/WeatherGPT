from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://weathergpt:weathergpt@db:5432/weathergpt"
    REDIS_URL: str = "redis://redis:6379/0"
    LLM_API_KEY: str = ""
    SECRET_KEY: str = "change-me"

    class Config:
        env_file = ".env"


settings = Settings()
