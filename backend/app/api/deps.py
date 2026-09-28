"""FastAPI dependencies that build services from settings and shared app state.

Tests override `get_http_client` (to mock every external API at once) and `get_settings`.
"""

from typing import Annotated

import httpx
from fastapi import Depends, Query, Request
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import InvalidRequestError
from app.schemas.climate import ClimateDateRange
from app.schemas.location import Location
from app.services.ai_service import AIService, build_ai_service
from app.services.alert_service import AlertService, build_alert_provider
from app.services.cache import InMemoryTTLCache
from app.services.chat_service import ChatService
from app.services.climate_service import ClimateService
from app.services.geocoding_service import GeocodingService, resolve_location
from app.services.weather_service import OpenMeteoProvider, WeatherService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def get_cache(request: Request) -> InMemoryTTLCache:
    return request.app.state.cache


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
CacheDep = Annotated[InMemoryTTLCache, Depends(get_cache)]


def get_weather_service(settings: SettingsDep, client: HttpClientDep, cache: CacheDep) -> WeatherService:
    provider = OpenMeteoProvider(client, settings.WEATHER_API_BASE_URL, settings.HTTP_TIMEOUT_SECONDS)
    return WeatherService(provider, cache, settings)


def get_geocoding_service(settings: SettingsDep, client: HttpClientDep, cache: CacheDep) -> GeocodingService:
    return GeocodingService(
        client,
        settings.GEOCODING_API_BASE_URL,
        cache,
        settings.GEOCODING_TTL_SECONDS,
        settings.HTTP_TIMEOUT_SECONDS,
    )


def get_climate_service(settings: SettingsDep, client: HttpClientDep, cache: CacheDep) -> ClimateService:
    return ClimateService(
        client,
        settings.CLIMATE_API_BASE_URL,
        cache,
        settings.CLIMATE_TTL_SECONDS,
        settings.HTTP_TIMEOUT_SECONDS,
    )


WeatherServiceDep = Annotated[WeatherService, Depends(get_weather_service)]
GeocodingServiceDep = Annotated[GeocodingService, Depends(get_geocoding_service)]


def get_alert_service(settings: SettingsDep, weather: WeatherServiceDep) -> AlertService:
    return AlertService(build_alert_provider(settings), weather)


def get_ai_service(settings: SettingsDep, client: HttpClientDep) -> AIService | None:
    # None (not configured) is reported by ChatService, after the request body has been validated.
    return build_ai_service(settings, client)


AlertServiceDep = Annotated[AlertService, Depends(get_alert_service)]


def get_chat_service(
    ai: Annotated[AIService | None, Depends(get_ai_service)],
    weather: WeatherServiceDep,
    geocoder: GeocodingServiceDep,
    alerts: AlertServiceDep,
) -> ChatService:
    return ChatService(ai, weather, geocoder, alerts)


async def get_requested_location(
    geocoder: GeocodingServiceDep,
    latitude: Annotated[float | None, Query(ge=-90, le=90, description="Latitude (-90 to 90)")] = None,
    longitude: Annotated[float | None, Query(ge=-180, le=180, description="Longitude (-180 to 180)")] = None,
    location_name: Annotated[
        str | None, Query(max_length=200, description="Display name to echo back when using coordinates")
    ] = None,
    query: Annotated[
        str | None, Query(min_length=2, max_length=100, description="Place name to geocode instead of coordinates")
    ] = None,
) -> Location:
    """Location from coordinates (preferred) or from a place-name query."""
    return await resolve_location(
        geocoder, latitude=latitude, longitude=longitude, query=query, location_name=location_name
    )


def get_date_range(
    start_date: Annotated[str, Query(description="YYYY-MM-DD", examples=["2025-06-01"])],
    end_date: Annotated[str, Query(description="YYYY-MM-DD", examples=["2025-09-30"])],
) -> ClimateDateRange:
    try:
        return ClimateDateRange(start_date=start_date, end_date=end_date)
    except ValidationError as exc:
        error = exc.errors()[0]
        message = error["msg"].removeprefix("Value error, ")
        field = ".".join(str(p) for p in error["loc"])
        raise InvalidRequestError(
            f"Invalid date range: {field + ': ' if field else ''}{message}", code="INVALID_DATE_RANGE"
        ) from exc


RequestedLocationDep = Annotated[Location, Depends(get_requested_location)]
