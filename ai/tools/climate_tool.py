import requests


def get_historical_weather(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str
) -> dict:
    """
    Fetch historical weather data for a location.

    Args:
        latitude: Location latitude.
        longitude: Location longitude.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns:
        A standardized historical weather dictionary.
    """

    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": (
            "temperature_2m_mean,"
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_sum,"
            "rain_sum"
        ),
        "timezone": "auto"
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        daily = data.get("daily", {})

        dates = daily.get("time", [])
        temperatures = daily.get("temperature_2m_mean", [])
        max_temperatures = daily.get("temperature_2m_max", [])
        min_temperatures = daily.get("temperature_2m_min", [])
        precipitation = daily.get("precipitation_sum", [])
        rain = daily.get("rain_sum", [])

        history = []

        for i, date in enumerate(dates):
            history.append({
                "date": date,
                "temperature_mean": temperatures[i],
                "temperature_max": max_temperatures[i],
                "temperature_min": min_temperatures[i],
                "precipitation": precipitation[i],
                "rain": rain[i]
            })

        return {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": data.get("timezone"),
            "start_date": start_date,
            "end_date": end_date,
            "history": history,
            "source": "Open-Meteo Historical Archive"
        }

    except requests.RequestException as error:
        return {
            "error": "Unable to retrieve historical weather data.",
            "details": str(error),
            "source": "Open-Meteo Historical Archive"
        }


# Test the climate tool
if __name__ == "__main__":
    climate = get_historical_weather(
        latitude=23.2599,
        longitude=77.4126,
        start_date="2026-09-01",
        end_date="2026-09-07"
    )

    print(climate)