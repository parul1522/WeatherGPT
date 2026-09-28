"""Historical weather (climate) schemas."""

import datetime as dt

from pydantic import BaseModel, Field, model_validator

from app.schemas.location import Location

EARLIEST_HISTORY_DATE = dt.date(1940, 1, 1)
MAX_HISTORY_DAYS = 366


class ClimateDateRange(BaseModel):
    start_date: dt.date
    end_date: dt.date

    @model_validator(mode="after")
    def _check_range(self) -> "ClimateDateRange":
        today = dt.date.today()
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        if self.end_date > today:
            raise ValueError("end_date cannot be in the future")
        if self.start_date < EARLIEST_HISTORY_DATE:
            raise ValueError(f"start_date cannot be before {EARLIEST_HISTORY_DATE.isoformat()}")
        if (self.end_date - self.start_date).days + 1 > MAX_HISTORY_DAYS:
            raise ValueError(f"date range cannot exceed {MAX_HISTORY_DAYS} days")
        return self


class ClimateUnits(BaseModel):
    temperature: str = "°C"
    precipitation: str = "mm"
    wind_speed: str = "km/h"


class ClimateDay(BaseModel):
    date: dt.date
    temperature_max: float | None = None
    temperature_min: float | None = None
    temperature_mean: float | None = None
    precipitation_sum: float | None = None
    wind_speed_max: float | None = None


class ClimatePeriodStats(BaseModel):
    days_with_data: int
    temperature_mean: float | None = None
    temperature_max: float | None = None
    temperature_min: float | None = None
    precipitation_total: float | None = None
    rainy_days: int = Field(description="Days with at least 2.5 mm rain (IMD rainy-day definition)")


class ClimateMonth(ClimatePeriodStats):
    month: str = Field(examples=["2025-07"])


class ClimateResponse(BaseModel):
    location: Location
    start_date: dt.date
    end_date: dt.date
    daily: list[ClimateDay]
    monthly: list[ClimateMonth]
    summary: ClimatePeriodStats
    units: ClimateUnits = Field(default_factory=ClimateUnits)
    source: str
    generated_at: dt.datetime
