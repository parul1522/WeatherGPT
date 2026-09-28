"""Async SQLAlchemy engine, session factory and FastAPI session dependency."""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_options() -> dict[str, Any]:
    settings = get_settings()
    options: dict[str, Any] = {"pool_pre_ping": True}
    if settings.is_postgres:
        # Fail fast when Postgres is down instead of hanging every request.
        options["connect_args"] = {"timeout": settings.DB_CONNECT_TIMEOUT_SECONDS}
    return options


engine = create_async_engine(get_settings().DATABASE_URL, **_engine_options())
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create tables if they do not exist. Adopt Alembic when the schema starts changing."""
    import app.models  # noqa: F401  (registers models on Base.metadata)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
