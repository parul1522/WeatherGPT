from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequestedLocationDep, WeatherServiceDep
from app.database.connection import get_db
from app.schemas.weather import WeatherCurrent, WeatherForecast

router = APIRouter(prefix="/weather", tags=["Weather"])


@router.get("/current", response_model=WeatherCurrent, summary="Current weather for a location")
async def current_weather(
    location: RequestedLocationDep,
    service: WeatherServiceDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WeatherCurrent:
    return await service.get_current(location, db)


@router.get("/forecast", response_model=WeatherForecast, summary="Daily and hourly forecast (1-7 days)")
async def weather_forecast(
    location: RequestedLocationDep,
    service: WeatherServiceDep,
    days: Annotated[int, Query(ge=1, le=7, description="Number of forecast days (1-7)")] = 3,
    include_hourly: Annotated[bool, Query(description="Include hourly rows")] = True,
) -> WeatherForecast:
    return await service.get_forecast(location, days, include_hourly)
