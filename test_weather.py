import asyncio
from weather_data.providers.open_meteo import get_forecast
from weather_data.processors.formatter import format_forecast


async def main():
    data = await get_forecast(
        lat=23.2599,
        lon=77.4126,
        days=7
    )

    formatted_data = format_forecast(data)
    print(formatted_data)   


asyncio.run(main())