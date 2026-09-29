import asyncio
from backend.weather_data.providers.open_meteo import get_forecast
from backend.weather_data.processors.formatter import format_forecast


async def main():
    data = await get_forecast(
        lat=23.2599,
        lon=77.4126,
        days=7
    )

    formatted_data = format_forecast(data)
    print(formatted_data)   


if __name__ == "__main__":
    # Live network smoke test (run from the project root):
    #   python -m scripts.smoke_open_meteo
    asyncio.run(main())
