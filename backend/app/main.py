"""WeatherGPT API entry point: app setup, routers, error handling and logging."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import alerts, chat, climate, location, weather
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import describe_secret, verify_api_key
from app.database.connection import close_db, init_db
from app.services.cache import InMemoryTTLCache
from app.services.http_client import create_http_client

settings = get_settings()

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
# httpx logs every request URL at INFO; keep it quiet so query strings don't flood the logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("app")


async def _init_db_with_retry(attempts: int = 5, delay_seconds: float = 2.0) -> None:
    # Postgres can take a few seconds to accept connections after `docker compose up`.
    for attempt in range(1, attempts + 1):
        try:
            await init_db()
            logger.info("Database ready")
            return
        except (SQLAlchemyError, OSError) as exc:
            if attempt == attempts:
                logger.error(
                    "Database initialisation failed (%s). Weather endpoints still work, but storing "
                    "data will fail until the database is reachable and the API is restarted.",
                    exc.__class__.__name__,
                )
                return
            logger.warning("Database not ready (%s), retrying in %.0fs", exc.__class__.__name__, delay_seconds)
            await asyncio.sleep(delay_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.http_client = create_http_client()
    app.state.cache = InMemoryTTLCache()
    await _init_db_with_retry()
    ai_key = {
        "groq": settings.GROQ_API_KEY,
        "openai": settings.OPENAI_API_KEY,
        "gemini": settings.GEMINI_API_KEY,
    }.get(settings.AI_PROVIDER)
    logger.info(
        "WeatherGPT API %s started (env=%s, ai_provider=%s, ai_key=%s, api_key_required=%s)",
        settings.APP_VERSION,
        settings.ENVIRONMENT,
        settings.AI_PROVIDER,
        describe_secret(ai_key) if settings.AI_PROVIDER != "none" else "n/a",
        settings.API_KEY is not None,
    )
    yield
    await app.state.http_client.aclose()
    await close_db()


app = FastAPI(
    title="WeatherGPT API",
    version=settings.APP_VERSION,
    description="Conversational weather intelligence backend for the WeatherGPT mobile app.",
    lifespan=lifespan,
)

origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials="*" not in origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next: Any) -> Any:
    started = time.perf_counter()
    response = await call_next(request)
    # Path only: query strings contain user locations.
    logger.info(
        "%s %s -> %s (%.0f ms)",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response


def error_response(status_code: int, code: str, message: str, details: list[dict[str, Any]] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=body)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.warning("%s on %s: %s", exc.code, request.url.path, exc.message)
    return error_response(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path", "header"))
        details.append({"field": field or "request", "message": str(error.get("msg", "")).removeprefix("Value error, ")})
    fields = {d["field"] for d in details}
    first = details[0] if details else {"field": "request", "message": "Invalid request"}
    if fields & {"latitude", "longitude"}:
        code, message = "INVALID_COORDINATES", f"Invalid coordinates: {first['field']} {first['message'].lower()}"
    else:
        code, message = "INVALID_REQUEST", f"Invalid value for '{first['field']}': {first['message']}"
    return error_response(400, code, message, details)


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
    return error_response(exc.status_code, code, str(exc.detail))


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return error_response(500, "INTERNAL_ERROR", "An unexpected error occurred. Please try again.")


@app.get("/health", tags=["Health"], summary="Liveness check")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "WeatherGPT API"}


API_PREFIX = "/api/v1"
for module in (weather, chat, alerts, climate, location):
    app.include_router(module.router, prefix=API_PREFIX, dependencies=[Depends(verify_api_key)])
