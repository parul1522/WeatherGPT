import requests


def get_current_weather(latitude: float, longitude: float) -> dict:
    """
    Fetch current weather data for a location.

    Args:
        latitude: Location latitude.
        longitude: Location longitude.

    Returns:
        A standardized weather dictionary.
    """

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "rain,"
            "weather_code,"
            "cloud_cover,"
            "wind_speed_10m,"
            "wind_direction_10m"
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

        current = data.get("current", {})

        return {
            "latitude": latitude,
            "longitude": longitude,
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "feels_like": current.get("apparent_temperature"),
            "precipitation": current.get("precipitation"),
            "rain": current.get("rain"),
            "weather_code": current.get("weather_code"),
            "cloud_cover": current.get("cloud_cover"),
            "wind_speed": current.get("wind_speed_10m"),
            "wind_direction": current.get("wind_direction_10m"),
            "timestamp": current.get("time"),
            "source": "Open-Meteo"
        }

    except requests.RequestException as error:
        return {
            "error": "Unable to retrieve weather data.",
            "details": str(error),
            "source": "Open-Meteo"
        }


# Test the weather tool
if __name__ == "__main__":
    weather = get_current_weather(
        latitude=23.2599,
        longitude=77.4126
    )

    print(weather)