from backend.weather_data.providers.open_meteo import get_forecast
from backend.weather_data.processors.formatter import format_forecast


async def get_weather(lat: float, lon: float, days: int = 7):
    data = await get_forecast(
        lat=lat,
        lon=lon,
        days=days
    )

    return format_forecast(data)