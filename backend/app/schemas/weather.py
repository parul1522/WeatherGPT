"""Normalized weather schemas. These are provider-independent: every provider maps into them."""

import datetime as dt

from pydantic import BaseModel, Field

from app.schemas.location import Location


class WeatherUnits(BaseModel):
    temperature: str = "°C"
    humidity: str = "%"
    wind_speed: str = "km/h"
    wind_direction: str = "°"
    precipitation: str = "mm"
    precipitation_probability: str = "%"


class CurrentConditions(BaseModel):
    temperature: float
    feels_like: float | None = None
    humidity: int | None = None
    wind_speed: float | None = None
    wind_direction: int | None = None
    precipitation: float | None = None
    weather_code: int | None = Field(default=None, description="WMO weather interpretation code")
    weather_description: str | None = None


class WeatherCurrent(BaseModel):
    location: Location
    current: CurrentConditions
    units: WeatherUnits = Field(default_factory=WeatherUnits)
    source: str
    updated_at: dt.datetime = Field(description="When the provider observed these conditions (UTC)")


class DailyForecast(BaseModel):
    date: dt.date
    weather_code: int | None = None
    weather_description: str | None = None
    temperature_max: float | None = None
    temperature_min: float | None = None
    precipitation_sum: float | None = None
    precipitation_probability_max: int | None = None
    wind_speed_max: float | None = None
    sunrise: dt.datetime | None = None
    sunset: dt.datetime | None = None


class HourlyForecast(BaseModel):
    time: dt.datetime
    temperature: float | None = None
    humidity: int | None = None
    precipitation: float | None = None
    precipitation_probability: int | None = None
    weather_code: int | None = None
    weather_description: str | None = None
    wind_speed: float | None = None


class WeatherForecast(BaseModel):
    location: Location
    timezone: str | None = Field(default=None, description="IANA timezone of the location, e.g. Asia/Kolkata")
    days: int
    daily: list[DailyForecast]
    hourly: list[HourlyForecast]
    units: WeatherUnits = Field(default_factory=WeatherUnits)
    source: str
    updated_at: dt.datetime = Field(description="When this forecast was fetched from the provider (UTC)")
