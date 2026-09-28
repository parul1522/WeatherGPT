def generate_advisory(weather_result: dict) -> str:
    """
    Generate a simple weather advisory from structured
    weather data.

    The advisory is based only on the weather data
    provided to this function.
    """

    # Check for errors
    if "error" in weather_result:
        return weather_result["error"]

    weather_data = weather_result.get("weather_data")

    if not weather_data:
        return "Weather data is not available."

    location = weather_result.get(
        "location",
        "your location"
    )

    intent = weather_result.get("intent")

    # -------------------------------------------------
    # CURRENT WEATHER
    # -------------------------------------------------

    if intent == "current_weather":

        temperature = weather_data.get(
            "temperature"
        )

        feels_like = weather_data.get(
            "feels_like"
        )

        humidity = weather_data.get(
            "humidity"
        )

        rain = weather_data.get(
            "rain"
        )

        wind_speed = weather_data.get(
            "wind_speed"
        )

        response = (
            f"Current weather in {location}:\n"
        )

        if temperature is not None:
            response += (
                f"Temperature: "
                f"{temperature}°C\n"
            )

        if feels_like is not None:
            response += (
                f"Feels like: "
                f"{feels_like}°C\n"
            )

        if humidity is not None:
            response += (
                f"Humidity: "
                f"{humidity}%\n"
            )

        if rain is not None:
            response += (
                f"Rain: "
                f"{rain} mm\n"
            )

        if wind_speed is not None:
            response += (
                f"Wind speed: "
                f"{wind_speed} km/h\n"
            )

        # Simple advisory rule
        if rain is not None and rain > 0:
            response += (
                "\nRain is currently being observed."
            )

        return response

    # -------------------------------------------------
    # FORECAST
    # -------------------------------------------------

    if intent == "forecast":

        # -------------------------------------------------
        # PERIOD FORECAST
        # -------------------------------------------------

        period_forecast = weather_data.get(
            "period_forecast"
        )

        if (
            period_forecast
            and period_forecast.get("status")
            == "available"
        ):

            date = period_forecast.get(
                "date"
            )

            time_range = period_forecast.get(
                "time_range"
            )

            temp_min = period_forecast.get(
                "temperature_min"
            )

            temp_max = period_forecast.get(
                "temperature_max"
            )

            rain_probability = period_forecast.get(
                "precipitation_probability_max"
            )

            precipitation = period_forecast.get(
                "precipitation_sum"
            )

            wind_speed = period_forecast.get(
                "wind_speed_max"
            )

            response = (
                f"Forecast for {location} "
                f"on {date}:\n"
            )

            if time_range:
                response += (
                    f"Time period: "
                    f"{time_range}\n"
                )

            if (
                temp_min is not None
                and temp_max is not None
            ):
                response += (
                    f"Temperature: "
                    f"{temp_min}°C – "
                    f"{temp_max}°C\n"
                )

            if rain_probability is not None:
                response += (
                    f"Rain probability: "
                    f"{rain_probability}%\n"
                )

            if precipitation is not None:
                response += (
                    f"Expected precipitation: "
                    f"{precipitation} mm\n"
                )

            if wind_speed is not None:
                response += (
                    f"Maximum wind speed: "
                    f"{wind_speed} km/h\n"
                )

            # Simple advisory
            if rain_probability is not None:

                if rain_probability >= 60:

                    response += (
                        "\nThere is a high chance "
                        "of rain. Consider carrying "
                        "an umbrella."
                    )

                elif rain_probability >= 30:

                    response += (
                        "\nThere is a moderate chance "
                        "of rain. Keep rain protection "
                        "available."
                    )

                else:

                    response += (
                        "\nThere is a low chance of rain "
                        "based on the available forecast."
                    )

            return response

        # -------------------------------------------------
        # DAILY FORECAST FALLBACK
        # -------------------------------------------------

        forecast = weather_data.get(
            "forecast",
            []
        )

        if not forecast:
            return (
                "Forecast data is not available."
            )

        # The first entry may represent today.
        # The second entry is normally tomorrow.
        if len(forecast) < 2:
            return (
                "Tomorrow's forecast is "
                "not available."
            )

        tomorrow = forecast[1]

        date = tomorrow.get(
            "date"
        )

        temp_max = tomorrow.get(
            "temperature_max"
        )

        temp_min = tomorrow.get(
            "temperature_min"
        )

        rain_probability = tomorrow.get(
            "precipitation_probability"
        )

        precipitation = tomorrow.get(
            "precipitation"
        )

        response = (
            f"Forecast for {location} "
            f"on {date}:\n"
        )

        if (
            temp_min is not None
            and temp_max is not None
        ):
            response += (
                f"Temperature: "
                f"{temp_min}°C – "
                f"{temp_max}°C\n"
            )

        if rain_probability is not None:
            response += (
                f"Rain probability: "
                f"{rain_probability}%\n"
            )

        if precipitation is not None:
            response += (
                f"Expected precipitation: "
                f"{precipitation} mm\n"
            )

        # Simple advisory
        if rain_probability is not None:

            if rain_probability >= 60:

                response += (
                    "\nThere is a high chance of rain. "
                    "Consider carrying an umbrella."
                )

            elif rain_probability >= 30:

                response += (
                    "\nThere is a moderate chance of rain. "
                    "Keep rain protection available."
                )

            else:

                response += (
                    "\nThere is a low chance of rain "
                    "based on the available forecast."
                )

        return response

    return "No advisory is available for this request."


# Test the advisory agent
if __name__ == "__main__":

    # -------------------------------------------------
    # CURRENT WEATHER TEST
    # -------------------------------------------------

    current_weather_result = {
        "location": "Bhopal",
        "intent": "current_weather",
        "weather_data": {
            "temperature": 24.2,
            "feels_like": 27.2,
            "humidity": 79,
            "rain": 0.0,
            "wind_speed": 7.1
        }
    }

    print(
        "\n--- CURRENT WEATHER ADVISORY ---"
    )

    print(
        generate_advisory(
            current_weather_result
        )
    )

    # -------------------------------------------------
    # DAILY FORECAST TEST
    # -------------------------------------------------

    forecast_result = {
        "location": "Bhopal",
        "intent": "forecast",
        "weather_data": {
            "forecast": [
                {
                    "date": "2026-09-28",
                    "temperature_max": 30.5,
                    "temperature_min": 21.6,
                    "precipitation_probability": 0,
                    "precipitation": 0.0
                },
                {
                    "date": "2026-09-29",
                    "temperature_max": 30.7,
                    "temperature_min": 21.9,
                    "precipitation_probability": 7,
                    "precipitation": 0.4
                }
            ]
        }
    }

    print(
        "\n--- DAILY FORECAST ADVISORY ---"
    )

    print(
        generate_advisory(
            forecast_result
        )
    )

    # -------------------------------------------------
    # PERIOD FORECAST TEST
    # -------------------------------------------------

    period_forecast_result = {
        "location": "Mumbai",
        "intent": "forecast",
        "weather_data": {
            "forecast": [
                {
                    "date": "2026-09-29",
                    "temperature_max": 31.2,
                    "temperature_min": 24.7,
                    "precipitation_probability": 90,
                    "precipitation": 3.0
                },
                {
                    "date": "2026-09-30",
                    "temperature_max": 31.0,
                    "temperature_min": 25.0,
                    "precipitation_probability": 80,
                    "precipitation": 4.0
                }
            ],

            "period_forecast": {
                "date": "2026-09-30",
                "time_range": "evening",
                "temperature_min": 26.4,
                "temperature_max": 29.3,
                "precipitation_probability_max": 76,
                "precipitation_sum": 0.5,
                "rain_sum": 0.5,
                "wind_speed_max": 12.0,
                "status": "available"
            }
        }
    }

    print(
        "\n--- PERIOD FORECAST ADVISORY ---"
    )

    print(
        generate_advisory(
            period_forecast_result
        )
    )