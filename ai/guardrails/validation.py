def validate_weather_data(weather_data: dict) -> dict:
    """
    Validate current weather data before it is used
    by the WeatherGPT response layer.
    """

    # Check whether the API returned an error
    if "error" in weather_data:
        return {
            "valid": False,
            "reason": weather_data["error"]
        }

    required_fields = [
        "temperature",
        "humidity",
        "precipitation",
        "wind_speed"
    ]

    missing_fields = []

    for field in required_fields:
        if weather_data.get(field) is None:
            missing_fields.append(field)

    if missing_fields:
        return {
            "valid": False,
            "reason": (
                "Missing weather data: "
                + ", ".join(missing_fields)
            )
        }

    # Basic range validation
    humidity = weather_data.get("humidity")

    if not 0 <= humidity <= 100:
        return {
            "valid": False,
            "reason": "Invalid humidity value."
        }

    precipitation = weather_data.get("precipitation")

    if precipitation < 0:
        return {
            "valid": False,
            "reason": "Invalid precipitation value."
        }

    wind_speed = weather_data.get("wind_speed")

    if wind_speed < 0:
        return {
            "valid": False,
            "reason": "Invalid wind speed value."
        }

    return {
        "valid": True,
        "reason": "Weather data is valid."
    }


def validate_forecast_data(weather_data: dict) -> dict:
    """
    Validate forecast data before it is used
    by the WeatherGPT response layer.
    """

    if "error" in weather_data:
        return {
            "valid": False,
            "reason": weather_data["error"]
        }

    forecast = weather_data.get("forecast")

    if not forecast:
        return {
            "valid": False,
            "reason": "Forecast data is empty."
        }

    for day in forecast:

        required_fields = [
            "date",
            "temperature_max",
            "temperature_min",
            "precipitation_probability",
            "precipitation"
        ]

        for field in required_fields:

            if day.get(field) is None:
                return {
                    "valid": False,
                    "reason": (
                        f"Missing forecast field: {field}"
                    )
                }

        probability = day.get(
            "precipitation_probability"
        )

        if not 0 <= probability <= 100:
            return {
                "valid": False,
                "reason": (
                    "Invalid precipitation probability."
                )
            }

        precipitation = day.get("precipitation")

        if precipitation < 0:
            return {
                "valid": False,
                "reason": "Invalid precipitation value."
            }

    return {
        "valid": True,
        "reason": "Forecast data is valid."
    }


# Test validation
if __name__ == "__main__":

    valid_weather = {
        "temperature": 24.2,
        "humidity": 79,
        "precipitation": 0.0,
        "wind_speed": 7.1
    }

    invalid_weather = {
        "temperature": None,
        "humidity": 150,
        "precipitation": -5,
        "wind_speed": -2
    }

    print("\n--- VALID WEATHER ---")
    print(validate_weather_data(valid_weather))

    print("\n--- INVALID WEATHER ---")
    print(validate_weather_data(invalid_weather))