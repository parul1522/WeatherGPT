"""Climate service: historical weather via the AI climate tool."""

from datetime import date

from ai.tools.climate_tool import get_historical_weather


def get_climate(lat: float, lon: float, start_date: str, end_date: str) -> dict:
    """Return historical daily weather. Raises ValueError on bad dates."""

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    if end < start:
        raise ValueError("end_date must not be before start_date.")

    return get_historical_weather(lat, lon, start_date, end_date)
