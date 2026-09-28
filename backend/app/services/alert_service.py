"""Official alerts + app-generated advisories.

Official alerts only ever come from an AlertProvider (e.g. a future IMD integration). Until one
is configured the API says so explicitly instead of implying "no warnings".

Advisories are simple threshold rules applied to forecast data. They are always labelled
`is_official: false` and must never be presented as warnings from a meteorological authority.
"""

import datetime as dt
import logging
from abc import ABC, abstractmethod

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AlertProviderError
from app.database import crud
from app.schemas.alert import Advisory, AlertItem, AlertResponse
from app.schemas.location import Location
from app.schemas.weather import DailyForecast, WeatherForecast
from app.services.weather_service import WeatherService

logger = logging.getLogger(__name__)

NO_PROVIDER_MESSAGE = "No alert provider configured."

# Daily rainfall thresholds follow IMD terminology (mm/day).
HEAVY_RAIN_MM = 64.5
VERY_HEAVY_RAIN_MM = 115.6
EXTREMELY_HEAVY_RAIN_MM = 204.5
HIGH_TEMPERATURE_C = 40.0
EXTREME_TEMPERATURE_C = 45.0
STRONG_WIND_KMH = 40.0
GALE_WIND_KMH = 62.0


class AlertProvider(ABC):
    """Interface for an official warning feed. Implementations return only official alerts."""

    name: str

    @abstractmethod
    async def fetch_alerts(self, latitude: float, longitude: float) -> list[AlertItem]: ...


def build_alert_provider(settings: Settings) -> AlertProvider | None:
    """Return the configured official alert provider, or None.

    "none" is currently the only option. To integrate IMD: implement AlertProvider, add its
    name to Settings.ALERT_PROVIDER, and return an instance here when selected.
    """
    if settings.ALERT_PROVIDER == "none":
        return None
    raise ValueError(f"Unknown ALERT_PROVIDER: {settings.ALERT_PROVIDER}")


def derive_advisories(daily: list[DailyForecast], source: str) -> list[Advisory]:
    basis = f"Derived by WeatherGPT from {source} forecast data. Not an official warning."
    advisories: list[Advisory] = []
    for day in daily:
        rain = day.precipitation_sum
        if rain is not None and rain >= HEAVY_RAIN_MM:
            if rain >= EXTREMELY_HEAVY_RAIN_MM:
                level, label = "extreme", "Extremely heavy rain"
            elif rain >= VERY_HEAVY_RAIN_MM:
                level, label = "high", "Very heavy rain"
            else:
                level, label = "moderate", "Heavy rain"
            advisories.append(
                Advisory(
                    advisory_type="heavy_rain",
                    level=level,
                    title=f"{label} possible",
                    description=f"Forecast rainfall of {rain} mm on {day.date.isoformat()}.",
                    date=day.date,
                    basis=basis,
                )
            )

        temp = day.temperature_max
        if temp is not None and temp >= HIGH_TEMPERATURE_C:
            level = "high" if temp >= EXTREME_TEMPERATURE_C else "moderate"
            advisories.append(
                Advisory(
                    advisory_type="high_temperature",
                    level=level,
                    title="High temperature expected",
                    description=f"Forecast maximum temperature of {temp} °C on {day.date.isoformat()}.",
                    date=day.date,
                    basis=basis,
                )
            )

        wind = day.wind_speed_max
        if wind is not None and wind >= STRONG_WIND_KMH:
            level = "high" if wind >= GALE_WIND_KMH else "moderate"
            advisories.append(
                Advisory(
                    advisory_type="strong_wind",
                    level=level,
                    title="Strong winds expected",
                    description=f"Forecast maximum wind speed of {wind} km/h on {day.date.isoformat()}.",
                    date=day.date,
                    basis=basis,
                )
            )
    return advisories


class AlertService:
    ADVISORY_FORECAST_DAYS = 3

    def __init__(self, provider: AlertProvider | None, weather_service: WeatherService) -> None:
        self._provider = provider
        self._weather = weather_service

    async def get_alerts(
        self,
        location: Location,
        db: AsyncSession | None,
        *,
        include_advisories: bool = False,
        forecast: WeatherForecast | None = None,
    ) -> AlertResponse:
        alerts, source, message = await self._official_alerts(location, db)

        advisories: list[Advisory] = []
        if include_advisories:
            if forecast is None:
                forecast = await self._weather.get_forecast(
                    location, self.ADVISORY_FORECAST_DAYS, include_hourly=False
                )
            advisories = derive_advisories(forecast.daily, forecast.source)

        return AlertResponse(
            location=location,
            alerts=alerts,
            advisories=advisories,
            source=source,
            message=message,
            generated_at=dt.datetime.now(dt.timezone.utc),
        )

    async def _official_alerts(
        self, location: Location, db: AsyncSession | None
    ) -> tuple[list[AlertItem], str | None, str | None]:
        if self._provider is None:
            return [], None, NO_PROVIDER_MESSAGE

        try:
            alerts = await self._provider.fetch_alerts(location.latitude, location.longitude)
        except AlertProviderError:
            logger.warning("Alert provider %s failed; falling back to stored alerts", self._provider.name)
            stored = await self._stored_alerts(location, db)
            return stored, self._provider.name, "Alert provider unavailable. Showing the last stored official alerts."

        if db is not None and alerts:
            try:
                await crud.save_alerts(
                    db, alerts, latitude=location.latitude, longitude=location.longitude, location_name=location.name
                )
            except (SQLAlchemyError, OSError) as exc:
                logger.warning("Could not store alerts: %s", exc.__class__.__name__)
                await crud.safe_rollback(db)
        return alerts, self._provider.name, None if alerts else "No active official alerts for this location."

    @staticmethod
    async def _stored_alerts(location: Location, db: AsyncSession | None) -> list[AlertItem]:
        if db is None:
            return []
        try:
            return await crud.get_active_alerts(db, latitude=location.latitude, longitude=location.longitude)
        except (SQLAlchemyError, OSError) as exc:
            logger.warning("Could not read stored alerts: %s", exc.__class__.__name__)
            await crud.safe_rollback(db)
            return []
