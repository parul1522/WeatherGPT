import httpx
from fastapi import APIRouter, HTTPException, Query

from backend.app.services.weather_service import get_weather

router = APIRouter()


@router.get("")
async def weather(
    lat: float = Query(...),
    lon: float = Query(...),
    days: int = Query(7)
):
    try:
        return await get_weather(
            lat=lat,
            lon=lon,
            days=days
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve weather data."
        )
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="Weather provider returned invalid data."
        )
