"""Alert schemas. Official alerts and app-generated advisories are deliberately separate types."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.location import Location


class AlertItem(BaseModel):
    """An official warning issued by a meteorological authority."""

    external_id: str | None = None
    alert_type: str
    severity: str
    title: str
    description: str | None = None
    source: str
    valid_from: dt.datetime | None = None
    valid_until: dt.datetime | None = None
    is_official: Literal[True] = True


class Advisory(BaseModel):
    """A rule-based notice computed by WeatherGPT from forecast data. Never an official warning."""

    advisory_type: Literal["heavy_rain", "high_temperature", "strong_wind"]
    level: Literal["moderate", "high", "extreme"]
    title: str
    description: str
    date: dt.date
    basis: str
    is_official: Literal[False] = False


class AlertResponse(BaseModel):
    location: Location
    alerts: list[AlertItem] = Field(description="Official alerts only")
    advisories: list[Advisory] = Field(description="App-generated advisories (not official warnings)")
    source: str | None = Field(description="Official alert provider, or null if none is configured")
    message: str | None = None
    generated_at: dt.datetime
