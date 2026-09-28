"""Open-Meteo provider (free, no API key)."""
import httpx

BASE_URL = "https://api.open-meteo.com/v1/forecast"


async def get_forecast(lat: float, lon: float, days: int = 7) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "forecast_days": days,
        "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(BASE_URL, params=params)
        r.raise_for_status()
        return r.json()
