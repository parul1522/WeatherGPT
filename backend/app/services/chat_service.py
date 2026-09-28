"""Chat orchestration: intent -> verified data -> answer.

Order matters: the AI only classifies the question, the backend fetches real data, and the AI
then phrases an answer from that data. If any step fails, an error is returned instead of a
guessed answer.
"""

import datetime as dt
import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AIServiceUnavailableError, InvalidRequestError
from app.database import crud
from app.schemas.chat import ChatRequest, ChatResponse, DataUsed, QueryIntent
from app.schemas.location import Location
from app.schemas.weather import WeatherForecast
from app.services.ai_service import AIService
from app.services.alert_service import AlertService
from app.services.geocoding_service import GeocodingService
from app.services.weather_service import WeatherService

logger = logging.getLogger(__name__)

FORECAST_DAYS_BY_RANGE = {"now": 1, "today": 1, "tomorrow": 2, "next_3_days": 3, "next_7_days": 7}
DEFAULT_FORECAST_DAYS = 3


class ChatService:
    def __init__(
        self,
        ai: AIService | None,
        weather: WeatherService,
        geocoder: GeocodingService,
        alerts: AlertService,
    ) -> None:
        self._ai = ai
        self._weather = weather
        self._geocoder = geocoder
        self._alerts = alerts

    async def answer(self, request: ChatRequest, db: AsyncSession | None) -> ChatResponse:
        if self._ai is None:
            raise AIServiceUnavailableError(
                "AI service is not configured. Set AI_PROVIDER and the matching API key.",
                code="AI_SERVICE_NOT_CONFIGURED",
            )
        intent = await self._ai.extract_intent(request.message)
        logger.info("Chat intent=%s time_range=%s", intent.intent, intent.time_range)

        location: Location | None = None
        verified: dict[str, Any] = {}
        sources: list[str] = []
        used = DataUsed()

        if intent.needs_weather_data:
            location = await self._resolve_location(request, intent)
            verified["location"] = location.model_dump(exclude_none=True)
            verified["request_time_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")

            if intent.requires_current_weather:
                current = await self._weather.get_current(location, db)
                verified["current_weather"] = current.model_dump(mode="json", exclude={"location"})
                used.weather = True
                sources.append(current.source)

            forecast: WeatherForecast | None = None
            if intent.requires_forecast or intent.requires_alerts:
                days = FORECAST_DAYS_BY_RANGE.get(intent.time_range or "", DEFAULT_FORECAST_DAYS)
                if not intent.requires_forecast:
                    days = AlertService.ADVISORY_FORECAST_DAYS
                forecast = await self._weather.get_forecast(location, days, include_hourly=True)
                sources.append(forecast.source)
                if intent.requires_forecast:
                    verified["forecast"] = _forecast_for_prompt(forecast, intent)
                    used.forecast = True

            if intent.requires_alerts:
                alert_response = await self._alerts.get_alerts(
                    location, db, include_advisories=True, forecast=forecast
                )
                verified["official_alerts"] = [a.model_dump(mode="json") for a in alert_response.alerts]
                verified["official_alert_status"] = alert_response.message or "Checked official alert provider."
                verified["app_advisories"] = [a.model_dump(mode="json") for a in alert_response.advisories]
                used.alerts = True
                if alert_response.source:
                    sources.append(alert_response.source)
        else:
            verified["note"] = "No weather data was fetched. Do not state any weather values."

        answer = await self._ai.generate_answer(request.message, request.language, verified)
        await self._store_conversation(db, request, intent, answer, location)

        return ChatResponse(
            answer=answer,
            language=request.language,
            intent=intent.intent,
            location=location,
            data_used=used,
            sources=list(dict.fromkeys(sources)),  # de-duplicate, keep order
            generated_at=dt.datetime.now(dt.timezone.utc),
        )

    async def _resolve_location(self, request: ChatRequest, intent: QueryIntent) -> Location:
        # A place named in the question beats the device's GPS ("rain in Mumbai?" asked from Bhopal).
        if intent.location:
            return await self._geocoder.geocode(intent.location)
        if request.latitude is not None and request.longitude is not None:
            return Location(name=request.location_name, latitude=request.latitude, longitude=request.longitude)
        raise InvalidRequestError(
            "Could not determine a location. Mention a city in the message or send latitude and longitude.",
            code="LOCATION_REQUIRED",
        )

    @staticmethod
    async def _store_conversation(
        db: AsyncSession | None,
        request: ChatRequest,
        intent: QueryIntent,
        answer: str,
        location: Location | None,
    ) -> None:
        if db is None:
            return
        try:
            await crud.save_conversation(
                db,
                message=request.message,
                answer=answer,
                language=request.language,
                intent=intent.model_dump(),
                session_id=request.session_id,
                location_name=location.name if location else None,
                latitude=location.latitude if location else None,
                longitude=location.longitude if location else None,
            )
        except (SQLAlchemyError, OSError) as exc:
            logger.warning("Could not store conversation: %s", exc.__class__.__name__)
            await crud.safe_rollback(db)


def _forecast_for_prompt(forecast: WeatherForecast, intent: QueryIntent) -> dict[str, Any]:
    """Keep the prompt small: all daily rows, plus hourly rows only for the day being asked about."""
    data: dict[str, Any] = {
        "timezone": forecast.timezone,
        "units": forecast.units.model_dump(),
        "daily": [d.model_dump(mode="json") for d in forecast.daily],
    }
    target_index = {"now": 0, "today": 0, None: 0, "tomorrow": 1}.get(intent.time_range)
    if target_index is not None and target_index < len(forecast.daily):
        target_date = forecast.daily[target_index].date
        data["hourly"] = [
            h.model_dump(mode="json", exclude={"weather_code"})
            for h in forecast.hourly
            if h.time.date() == target_date
        ]
    return data

