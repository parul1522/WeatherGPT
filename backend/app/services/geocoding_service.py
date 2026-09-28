"""Place-name geocoding using the free Open-Meteo Geocoding API (no key required).

Results are cached for a day to keep request volume well within the free-tier fair-use limits.
"""

import logging
from typing import Any

import httpx

from app.core.exceptions import GeocodingProviderError, InvalidRequestError, LocationNotFoundError
from app.schemas.location import Location
from app.services.cache import InMemoryTTLCache
from app.services.http_client import request_json

logger = logging.getLogger(__name__)


class GeocodingService:
    source = "Open-Meteo Geocoding"

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        cache: InMemoryTTLCache,
        ttl_seconds: int,
        timeout: float,
    ) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/search"
        self._cache = cache
        self._ttl = ttl_seconds
        self._timeout = timeout

    async def geocode(self, query: str, language: str = "en") -> Location:
        cleaned = " ".join(query.split())
        if len(cleaned) < 2:
            raise InvalidRequestError("Location query must be at least 2 characters.")

        key = f"geocode:{language}:{cleaned.lower()}"
        cached: Location | None = await self._cache.get(key)
        if cached is not None:
            return cached

        location = await self._lookup(cleaned, language)
        await self._cache.set(key, location, self._ttl)
        return location

    async def _lookup(self, query: str, language: str) -> Location:
        # The API matches place names only, so "Bhopal, Madhya Pradesh" is searched as "Bhopal"
        # and the remaining parts are used to pick the right match (state or country).
        parts = [p.strip() for p in query.split(",") if p.strip()]
        name, qualifiers = parts[0], [q.lower() for q in parts[1:]]

        data = await request_json(
            self._client,
            "GET",
            self._url,
            params={"name": name, "count": 10 if qualifiers else 1, "language": language, "format": "json"},
            timeout=self._timeout,
            service_name="Geocoding service",
            error_cls=GeocodingProviderError,
        )
        results = [r for r in data.get("results") or [] if self._is_valid(r)]
        if not results:
            raise LocationNotFoundError(f"Could not find a location named '{query}'.")

        best = results[0]
        if qualifiers:
            for result in results:
                haystack = " ".join(
                    str(result.get(field) or "").lower() for field in ("country", "admin1", "admin2", "country_code")
                )
                if all(q in haystack for q in qualifiers):
                    best = result
                    break

        return Location(
            name=best["name"],
            latitude=round(float(best["latitude"]), 4),
            longitude=round(float(best["longitude"]), 4),
            country=best.get("country"),
            state=best.get("admin1"),
        )

    @staticmethod
    def _is_valid(result: Any) -> bool:
        if not isinstance(result, dict) or not isinstance(result.get("name"), str):
            return False
        lat, lon = result.get("latitude"), result.get("longitude")
        return (
            isinstance(lat, (int, float))
            and isinstance(lon, (int, float))
            and -90 <= lat <= 90
            and -180 <= lon <= 180
        )


async def resolve_location(
    geocoder: GeocodingService,
    *,
    latitude: float | None,
    longitude: float | None,
    query: str | None,
    location_name: str | None,
) -> Location:
    """Coordinates win when given; otherwise the place-name query is geocoded."""
    if (latitude is None) != (longitude is None):
        raise InvalidRequestError(
            "Invalid coordinates: latitude and longitude must be provided together.",
            code="INVALID_COORDINATES",
        )
    if latitude is not None and longitude is not None:
        return Location(name=location_name, latitude=latitude, longitude=longitude)
    if query:
        return await geocoder.geocode(query)
    raise InvalidRequestError(
        "Provide latitude and longitude, or a place name in 'query'.", code="LOCATION_REQUIRED"
    )
