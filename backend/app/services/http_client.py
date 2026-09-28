"""Shared outbound HTTP helpers: one AsyncClient per app, and uniform error mapping."""

import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


def create_http_client() -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=settings.HTTP_TIMEOUT_SECONDS,
        headers={"User-Agent": f"WeatherGPT/{settings.APP_VERSION} (Smart India Hackathon prototype)"},
        follow_redirects=True,
    )


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    service_name: str,
    error_cls: type[ExternalServiceError],
    timeout: float,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Send a request and return the decoded JSON object.

    Any network problem, non-2xx status or non-JSON body raises `error_cls` with a user-safe
    message; the technical detail goes to the log only.
    """
    try:
        response = await client.request(method, url, params=params, json=json, headers=headers, timeout=timeout)
    except httpx.TimeoutException as exc:
        logger.warning("%s timed out: %s", service_name, exc.__class__.__name__)
        raise error_cls(f"{service_name} timed out. Please try again.") from exc
    except httpx.HTTPError as exc:
        logger.warning("%s request failed: %s", service_name, exc.__class__.__name__)
        raise error_cls(f"{service_name} is unreachable. Please try again shortly.") from exc

    if response.status_code == 429:
        logger.warning("%s rate limit reached", service_name)
        raise error_cls(f"{service_name} rate limit reached. Please try again shortly.")
    if response.status_code >= 400:
        logger.error("%s returned HTTP %s: %s", service_name, response.status_code, response.text[:300])
        raise error_cls()

    try:
        data = response.json()
    except ValueError as exc:
        logger.error("%s returned a non-JSON body", service_name)
        raise error_cls(f"{service_name} returned an invalid response.") from exc
    if not isinstance(data, dict):
        logger.error("%s returned JSON that is not an object", service_name)
        raise error_cls(f"{service_name} returned an invalid response.")
    return data
