"""Historical weather from the Open-Meteo Historical (archive) API, with simple aggregates.

The monthly/summary statistics here are plain averages and totals. Trend analysis (e.g. yearly
rainfall trends) can be added as further functions over the same `ClimateDay` list.
"""

import datetime as dt
import logging
from collections import defaultdict
from statistics import mean

import httpx

from app.core.exceptions import WeatherProviderError
from app.schemas.climate import ClimateDateRange, ClimateDay, ClimateMonth, ClimatePeriodStats, ClimateResponse
from app.schemas.location import Location
from app.services.cache import InMemoryTTLCache
from app.services.http_client import request_json

logger = logging.getLogger(__name__)

RAINY_DAY_MM = 2.5  # IMD definition of a rainy day


def _round(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None


def summarize(days: list[ClimateDay]) -> ClimatePeriodStats:
    means = [d.temperature_mean for d in days if d.temperature_mean is not None]
    maxes = [d.temperature_max for d in days if d.temperature_max is not None]
    mins = [d.temperature_min for d in days if d.temperature_min is not None]
    rain = [d.precipitation_sum for d in days if d.precipitation_sum is not None]
    return ClimatePeriodStats(
        days_with_data=sum(1 for d in days if d.temperature_mean is not None or d.precipitation_sum is not None),
        temperature_mean=_round(mean(means)) if means else None,
        temperature_max=max(maxes) if maxes else None,
        temperature_min=min(mins) if mins else None,
        precipitation_total=_round(sum(rain)) if rain else None,
        rainy_days=sum(1 for r in rain if r >= RAINY_DAY_MM),
    )


def monthly_breakdown(days: list[ClimateDay]) -> list[ClimateMonth]:
    by_month: dict[str, list[ClimateDay]] = defaultdict(list)
    for day in days:
        by_month[day.date.strftime("%Y-%m")].append(day)
    return [ClimateMonth(month=month, **summarize(items).model_dump()) for month, items in sorted(by_month.items())]


class ClimateService:
    source = "Open-Meteo Historical"

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        cache: InMemoryTTLCache,
        ttl_seconds: int,
        timeout: float,
    ) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/archive"
        self._cache = cache
        self._ttl = ttl_seconds
        self._timeout = timeout

    async def get_history(self, location: Location, date_range: ClimateDateRange) -> ClimateResponse:
        key = (
            f"climate:{location.latitude:.2f}:{location.longitude:.2f}:"
            f"{date_range.start_date.isoformat()}:{date_range.end_date.isoformat()}"
        )
        days: list[ClimateDay] | None = await self._cache.get(key)
        if days is None:
            days = await self._fetch_days(location, date_range)
            await self._cache.set(key, days, self._ttl)

        return ClimateResponse(
            location=location,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
            daily=days,
            monthly=monthly_breakdown(days),
            summary=summarize(days),
            source=self.source,
            generated_at=dt.datetime.now(dt.timezone.utc),
        )

    async def _fetch_days(self, location: Location, date_range: ClimateDateRange) -> list[ClimateDay]:
        data = await request_json(
            self._client,
            "GET",
            self._url,
            params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "start_date": date_range.start_date.isoformat(),
                "end_date": date_range.end_date.isoformat(),
                "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max",
                "timezone": "auto",
                "wind_speed_unit": "kmh",
            },
            timeout=self._timeout,
            service_name="Historical weather provider",
            error_cls=WeatherProviderError,
        )
        daily = data.get("daily")
        if not isinstance(daily, dict) or not isinstance(daily.get("time"), list):
            logger.error("Open-Meteo archive response missing 'daily.time'")
            raise WeatherProviderError("Historical weather provider returned incomplete data.")

        def value(key: str, i: int) -> float | None:
            values = daily.get(key)
            item = values[i] if isinstance(values, list) and i < len(values) else None
            return round(float(item), 1) if isinstance(item, (int, float)) and not isinstance(item, bool) else None

        try:
            return [
                ClimateDay(
                    date=dt.date.fromisoformat(day),
                    temperature_max=value("temperature_2m_max", i),
                    temperature_min=value("temperature_2m_min", i),
                    temperature_mean=value("temperature_2m_mean", i),
                    precipitation_sum=value("precipitation_sum", i),
                    wind_speed_max=value("wind_speed_10m_max", i),
                )
                for i, day in enumerate(daily["time"])
            ]
        except (ValueError, TypeError) as exc:
            logger.error("Could not parse Open-Meteo archive data: %s", exc)
            raise WeatherProviderError("Historical weather provider returned invalid data.") from exc
