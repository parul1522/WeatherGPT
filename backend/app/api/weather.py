from fastapi import APIRouter, Query
from app.services.weather_service import get_weather

router = APIRouter()


@router.get("")
async def weather(
    lat: float = Query(...),
    lon: float = Query(...),
    days: int = Query(7)
):
    return await get_weather(
        lat=lat,
        lon=lon,
        days=days
    )