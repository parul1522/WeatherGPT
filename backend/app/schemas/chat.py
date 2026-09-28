"""Chat request/response schemas and the validated structure of an AI-extracted intent."""

import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

from app.schemas.location import Latitude, Location, Longitude

IntentName = Literal["current_weather", "forecast", "alerts", "general"]
TimeRange = Literal["now", "today", "tomorrow", "next_3_days", "next_7_days"]


class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    language: Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}(-[A-Za-z]{2})?$")] = "en"
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    location_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    session_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"message": "Will it rain tomorrow in Bhopal?", "language": "en", "latitude": None, "longitude": None}
            ]
        }
    )

    @model_validator(mode="after")
    def _coordinates_together(self) -> "ChatRequest":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class DataUsed(BaseModel):
    weather: bool = False
    forecast: bool = False
    alerts: bool = False


class ChatResponse(BaseModel):
    answer: str
    language: str
    intent: IntentName
    location: Location | None
    data_used: DataUsed
    sources: list[str]
    generated_at: dt.datetime


class QueryIntent(BaseModel):
    """Structured output the LLM must produce. Anything that does not validate is rejected."""

    model_config = ConfigDict(extra="ignore")

    intent: IntentName
    location: str | None = None
    time_range: TimeRange | None = None
    requires_current_weather: bool = False
    requires_forecast: bool = False
    requires_alerts: bool = False

    @field_validator("location", mode="before")
    @classmethod
    def _clean_location(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value or value.lower() in {"null", "none", "here", "my location", "current location"}:
                return None
            return value[:100]
        return value

    @model_validator(mode="after")
    def _make_flags_consistent(self) -> "QueryIntent":
        # Don't trust the LLM to keep flags consistent with the intent; derive the required ones.
        if self.intent == "current_weather":
            self.requires_current_weather = True
        elif self.intent == "forecast":
            self.requires_forecast = True
        elif self.intent == "alerts":
            self.requires_alerts = True
        if self.time_range in {"tomorrow", "next_3_days", "next_7_days"} and self.intent != "general":
            self.requires_forecast = True
        return self

    @property
    def needs_weather_data(self) -> bool:
        return self.requires_current_weather or self.requires_forecast or self.requires_alerts
