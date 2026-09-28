"""Weather data access.

WeatherService (cache + persistence) talks to a WeatherProvider. OpenMeteoProvider is the
first implementation; an IMD provider only needs to implement the same two methods and
return the same normalized schemas, so the API contract seen by the app never changes.
"""

import datetime as dt
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import WeatherProviderError
from app.database import crud
from app.schemas.location import Location
from app.schemas.weather import (
    CurrentConditions,
    DailyForecast,
    HourlyForecast,
    WeatherCurrent,
    WeatherForecast,
)
from app.services.cache import InMemoryTTLCache
from app.services.http_client import request_json

logger = logging.getLogger(__name__)

# WMO weather interpretation codes (used by Open-Meteo and many other providers).
WMO_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe_weather_code(code: int | None) -> str | None:
    return WMO_DESCRIPTIONS.get(code) if code is not None else None


@dataclass(frozen=True)
class CurrentObservation:
    conditions: CurrentConditions
    observed_at: dt.datetime  # UTC
    source: str


@dataclass(frozen=True)
class ForecastData:
    timezone: str | None
    daily: list[DailyForecast]
    hourly: list[HourlyForecast]
    source: str
    fetched_at: dt.datetime  # UTC


class WeatherProvider(ABC):
    name: str

    @abstractmethod
    async def fetch_current(self, latitude: float, longitude: float) -> CurrentObservation: ...

    @abstractmethod
    async def fetch_forecast(
        self, latitude: float, longitude: float, days: int, include_hourly: bool
    ) -> ForecastData: ...


# ---------- value helpers (tolerate missing / null provider fields) ----------

def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _float(value: Any) -> float | None:
    return round(float(value), 1) if _is_number(value) else None


def _int(value: Any) -> int | None:
    return int(round(value)) if _is_number(value) else None


def _at(block: dict[str, Any], key: str, index: int) -> Any:
    values = block.get(key)
    if isinstance(values, list) and index < len(values):
        return values[index]
    return None


def _local_datetime(value: Any, utc_offset_seconds: int) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone(dt.timedelta(seconds=utc_offset_seconds)))
    return parsed


class OpenMeteoProvider(WeatherProvider):
    name = "Open-Meteo"

    _CURRENT_VARS = (
        "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,"
        "weather_code,wind_speed_10m,wind_direction_10m"
    )
    _DAILY_VARS = (
        "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "precipitation_probability_max,wind_speed_10m_max,sunrise,sunset"
    )
    _HOURLY_VARS = (
        "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,"
        "weather_code,wind_speed_10m"
    )

    def __init__(self, client: httpx.AsyncClient, base_url: str, timeout: float) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/forecast"
        self._timeout = timeout

    async def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        return await request_json(
            self._client,
            "GET",
            self._url,
            params=params,
            timeout=self._timeout,
            service_name="Weather provider",
            error_cls=WeatherProviderError,
        )

    async def fetch_current(self, latitude: float, longitude: float) -> CurrentObservation:
        data = await self._get(
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": self._CURRENT_VARS,
                "timezone": "auto",
                "wind_speed_unit": "kmh",
            }
        )
        current = data.get("current")
        if not isinstance(current, dict) or not _is_number(current.get("temperature_2m")):
            logger.error("Open-Meteo current response missing 'current.temperature_2m'")
            raise WeatherProviderError("Weather provider returned incomplete data.")

        offset = _int(data.get("utc_offset_seconds")) or 0
        try:
            observed_local = _local_datetime(current.get("time"), offset)
        except ValueError:
            observed_local = None
        observed_at = (observed_local or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)

        code = _int(current.get("weather_code"))
        conditions = CurrentConditions(
            temperature=_float(current["temperature_2m"]),
            feels_like=_float(current.get("apparent_temperature")),
            humidity=_int(current.get("relative_humidity_2m")),
            wind_speed=_float(current.get("wind_speed_10m")),
            wind_direction=_int(current.get("wind_direction_10m")),
            precipitation=_float(current.get("precipitation")),
            weather_code=code,
            weather_description=describe_weather_code(code),
        )
        return CurrentObservation(conditions=conditions, observed_at=observed_at, source=self.name)

    async def fetch_forecast(
        self, latitude: float, longitude: float, days: int, include_hourly: bool
    ) -> ForecastData:
        params: dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": self._DAILY_VARS,
            "forecast_days": days,
            "timezone": "auto",
            "wind_speed_unit": "kmh",
        }
        if include_hourly:
            params["hourly"] = self._HOURLY_VARS
        data = await self._get(params)

        daily_block = data.get("daily")
        if not isinstance(daily_block, dict) or not isinstance(daily_block.get("time"), list):
            logger.error("Open-Meteo forecast response missing 'daily.time'")
            raise WeatherProviderError("Weather provider returned incomplete data.")
        offset = _int(data.get("utc_offset_seconds")) or 0

        try:
            daily = [self._parse_day(daily_block, i, offset) for i in range(len(daily_block["time"]))]
            hourly: list[HourlyForecast] = []
            hourly_block = data.get("hourly")
            if include_hourly and isinstance(hourly_block, dict) and isinstance(hourly_block.get("time"), list):
                hourly = [self._parse_hour(hourly_block, i, offset) for i in range(len(hourly_block["time"]))]
        except (ValueError, TypeError) as exc:
            logger.error("Could not parse Open-Meteo forecast: %s", exc)
            raise WeatherProviderError("Weather provider returned invalid data.") from exc

        timezone_name = data.get("timezone") if isinstance(data.get("timezone"), str) else None
        return ForecastData(
            timezone=timezone_name,
            daily=daily,
            hourly=hourly,
            source=self.name,
            fetched_at=dt.datetime.now(dt.timezone.utc),
        )

    @staticmethod
    def _parse_day(block: dict[str, Any], i: int, offset: int) -> DailyForecast:
        code = _int(_at(block, "weather_code", i))
        return DailyForecast(
            date=dt.date.fromisoformat(block["time"][i]),
            weather_code=code,
            weather_description=describe_weather_code(code),
            temperature_max=_float(_at(block, "temperature_2m_max", i)),
            temperature_min=_float(_at(block, "temperature_2m_min", i)),
            precipitation_sum=_float(_at(block, "precipitation_sum", i)),
            precipitation_probability_max=_int(_at(block, "precipitation_probability_max", i)),
            wind_speed_max=_float(_at(block, "wind_speed_10m_max", i)),
            sunrise=_local_datetime(_at(block, "sunrise", i), offset),
            sunset=_local_datetime(_at(block, "sunset", i), offset),
        )

    @staticmethod
    def _parse_hour(block: dict[str, Any], i: int, offset: int) -> HourlyForecast:
        code = _int(_at(block, "weather_code", i))
        time = _local_datetime(block["time"][i], offset)
        if time is None:
            raise ValueError("hourly time is not a string")
        return HourlyForecast(
            time=time,
            temperature=_float(_at(block, "temperature_2m", i)),
            humidity=_int(_at(block, "relative_humidity_2m", i)),
            precipitation=_float(_at(block, "precipitation", i)),
            precipitation_probability=_int(_at(block, "precipitation_probability", i)),
            weather_code=code,
            weather_description=describe_weather_code(code),
            wind_speed=_float(_at(block, "wind_speed_10m", i)),
        )


class WeatherService:
    """Current weather: memory cache -> recent DB row -> provider. Forecast: memory cache -> provider."""

    def __init__(self, provider: WeatherProvider, cache: InMemoryTTLCache, settings: Settings) -> None:
        self._provider = provider
        self._cache = cache
        self._current_ttl = settings.CURRENT_WEATHER_TTL_SECONDS
        self._forecast_ttl = settings.FORECAST_TTL_SECONDS

    async def get_current(self, location: Location, db: AsyncSession | None = None) -> WeatherCurrent:
        # Rounding to 2 decimals (~1 km) lets nearby users share cache entries.
        key = f"weather:current:{location.latitude:.2f}:{location.longitude:.2f}"
        observation: CurrentObservation | None = await self._cache.get(key)

        if observation is None and db is not None and self._current_ttl > 0:
            observation, age_seconds = await self._load_recent(db, location)
            if observation is not None:
                await self._cache.set(key, observation, self._current_ttl - age_seconds)

        if observation is None:
            observation = await self._provider.fetch_current(location.latitude, location.longitude)
            await self._cache.set(key, observation, self._current_ttl)
            if db is not None:
                await self._persist(db, location, observation)

        return WeatherCurrent(
            location=location,
            current=observation.conditions,
            source=observation.source,
            updated_at=observation.observed_at,
        )

    async def get_forecast(self, location: Location, days: int, include_hourly: bool = True) -> WeatherForecast:
        key = f"weather:forecast:{location.latitude:.2f}:{location.longitude:.2f}:{days}:{int(include_hourly)}"
        forecast: ForecastData | None = await self._cache.get(key)
        if forecast is None:
            forecast = await self._provider.fetch_forecast(
                location.latitude, location.longitude, days, include_hourly
            )
            await self._cache.set(key, forecast, self._forecast_ttl)

        return WeatherForecast(
            location=location,
            timezone=forecast.timezone,
            days=days,
            daily=forecast.daily,
            hourly=forecast.hourly,
            source=forecast.source,
            updated_at=forecast.fetched_at,
        )

    async def _load_recent(
        self, db: AsyncSession, location: Location
    ) -> tuple[CurrentObservation | None, float]:
        try:
            record = await crud.get_recent_weather(
                db,
                latitude=location.latitude,
                longitude=location.longitude,
                max_age_seconds=self._current_ttl,
            )
        except (SQLAlchemyError, OSError) as exc:
            logger.warning("Weather cache lookup in database failed: %s", exc.__class__.__name__)
            await crud.safe_rollback(db)
            return None, 0.0
        if record is None:
            return None, 0.0

        conditions = CurrentConditions(
            temperature=record.temperature,
            feels_like=record.feels_like,
            humidity=record.humidity,
            wind_speed=record.wind_speed,
            wind_direction=record.wind_direction,
            precipitation=record.precipitation,
            weather_code=record.weather_code,
            weather_description=describe_weather_code(record.weather_code),
        )
        age = (dt.datetime.now(dt.timezone.utc) - record.created_at).total_seconds()
        return CurrentObservation(conditions, record.observed_at, record.source), max(age, 0.0)

    async def _persist(self, db: AsyncSession, location: Location, observation: CurrentObservation) -> None:
        try:
            await crud.save_weather(
                db,
                latitude=location.latitude,
                longitude=location.longitude,
                location_name=location.name,
                conditions=observation.conditions,
                observed_at=observation.observed_at,
                source=observation.source,
            )
        except (SQLAlchemyError, OSError) as exc:
            # Persistence is best-effort: the user still gets live weather if the DB is down.
            logger.warning("Could not store weather observation: %s", exc.__class__.__name__)
            await crud.safe_rollback(db)
