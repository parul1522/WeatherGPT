import re


# --------------------------------------------------
# NUMBER EXTRACTION
# --------------------------------------------------

def extract_numbers(text: str) -> list:
    """
    Extract numerical values from a response.

    Examples:

        "95% chance of rain"
        -> [95.0]

        "26.4°C to 29.3°C"
        -> [26.4, 29.3]

        "0 mm"
        -> [0.0]
    """

    if not text:
        return []

    matches = re.findall(
        r"(?<![\d.])-?\d+(?:\.\d+)?",
        text
    )

    numbers = []

    for value in matches:

        try:
            numbers.append(
                float(value)
            )

        except ValueError:
            continue

    return numbers


# --------------------------------------------------
# NUMBER COMPARISON
# --------------------------------------------------

def number_matches(
    response_number: float,
    verified_number
) -> bool:
    """
    Compare a response number with a verified
    weather number.

    Uses a small tolerance for floating-point values.
    """

    try:

        verified_number = float(
            verified_number
        )

    except (TypeError, ValueError):

        return False

    return abs(
        response_number - verified_number
    ) < 0.0001


# --------------------------------------------------
# NUMBERS THAT ARE NOT WEATHER VALUES
# --------------------------------------------------

_NON_WEATHER_NUMBER_PATTERNS = [
    # ISO dates: 2026-09-29
    r"\b\d{4}-\d{2}-\d{2}\b",
    # clock times: 6:00, 18:30
    r"\b\d{1,2}:\d{2}\b",
    # 6 AM, 11 pm
    r"\b\d{1,2}\s?(?:am|pm)\b",
    # durations: 7 days, 24-hour, 3 hours
    r"\b\d+\s?-?\s?(?:days?|hours?|hrs?)\b",
]


def strip_non_weather_numbers(text: str) -> str:
    """
    Remove dates, clock times and durations so that only numbers
    that claim to be weather values are checked.
    """

    if not text:
        return ""

    for pattern in _NON_WEATHER_NUMBER_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    # "24-33" is a range, not a negative number
    return re.sub(r"(?<=\d)-(?=\d)", " ", text)


def is_number_supported(
    response_number: float,
    verified_values: list
) -> bool:
    """
    A response number is supported when it equals a verified value, or
    - if it is written as a whole number - when it is that value
    rounded (e.g. "30" for 29.8).
    """

    for verified in verified_values:

        if number_matches(response_number, verified):
            return True

        if (
            float(response_number).is_integer()
            and abs(response_number - verified) < 0.5
        ):
            return True

    return False


def find_unsupported_numbers(
    response_numbers: list,
    verified_values: list
) -> list:
    """Return every response number not backed by verified data."""

    return [
        number
        for number in response_numbers
        if not is_number_supported(number, verified_values)
    ]


# --------------------------------------------------
# CURRENT WEATHER CHECK
# --------------------------------------------------

def check_current_weather_response(
    response: str,
    weather_data: dict
) -> dict:
    """
    Check whether a current-weather response contains
    information supported by the provided data.
    """

    if not response:

        return {
            "safe": False,
            "reason": "Response is empty."
        }

    if not weather_data:

        return {
            "safe": False,
            "reason": "Weather data is unavailable."
        }

    if "error" in weather_data:

        return {
            "safe": False,
            "reason": "Weather data contains an error."
        }

    # --------------------------------------------------
    # EXTRACT NUMBERS FROM RESPONSE
    # --------------------------------------------------

    response_numbers = extract_numbers(
        strip_non_weather_numbers(response)
    )

    if not response_numbers:

        return {
            "safe": False,
            "reason": (
                "Response does not contain "
                "verified numerical weather information."
            )
        }

    # --------------------------------------------------
    # ONLY USE ACTUAL WEATHER VALUES
    # --------------------------------------------------

    weather_fields = [
        "temperature",
        "humidity",
        "feels_like",
        "precipitation",
        "rain",
        "wind_speed",
        "wind_direction",
        "cloud_cover"
    ]

    verified_values = []

    for field in weather_fields:

        value = weather_data.get(
            field
        )

        if value is not None:

            try:

                verified_values.append(
                    float(value)
                )

            except (TypeError, ValueError):

                continue

    # --------------------------------------------------
    # COMPARE NUMBERS
    # --------------------------------------------------

    # Every number in the response must be backed by the data.
    # (Previously a single coincidental match made the whole
    # response "safe", so fabricated values could slip through.)
    unsupported = find_unsupported_numbers(
        response_numbers,
        verified_values
    )

    if unsupported:

        return {
            "safe": False,
            "reason": (
                "Response contains numbers that are not "
                "in the verified weather data: "
                + ", ".join(str(n) for n in unsupported)
            )
        }

    return {
        "safe": True,
        "reason": (
            "Response is supported by "
            "verified weather data."
        )
    }


# --------------------------------------------------
# FORECAST CHECK
# --------------------------------------------------

def check_forecast_response(
    response: str,
    forecast_data: dict
) -> dict:
    """
    Check whether a forecast response contains
    information supported by the forecast data.

    Supports:

        1. Daily forecast
        2. Period forecast
        3. Hourly period forecast
    """

    if not response:

        return {
            "safe": False,
            "reason": "Response is empty."
        }

    if not forecast_data:

        return {
            "safe": False,
            "reason": "Forecast data is unavailable."
        }

    if "error" in forecast_data:

        return {
            "safe": False,
            "reason": "Forecast data contains an error."
        }

    # --------------------------------------------------
    # EXTRACT NUMBERS FROM RESPONSE
    # --------------------------------------------------

    response_numbers = extract_numbers(
        strip_non_weather_numbers(response)
    )

    if not response_numbers:

        return {
            "safe": False,
            "reason": (
                "Response does not contain "
                "verified numerical forecast information."
            )
        }

    # --------------------------------------------------
    # VERIFIED FORECAST VALUES
    # --------------------------------------------------

    verified_values = []

    # --------------------------------------------------
    # DAILY FORECAST
    # --------------------------------------------------

    forecast = forecast_data.get(
        "forecast",
        []
    )

    for day in forecast:

        fields = [
            "temperature_max",
            "temperature_min",
            "precipitation_probability",
            "precipitation",
            "wind_speed_max"
        ]

        for field in fields:

            value = day.get(
                field
            )

            if value is not None:

                try:

                    verified_values.append(
                        float(value)
                    )

                except (TypeError, ValueError):

                    continue

    # --------------------------------------------------
    # PERIOD FORECAST
    # --------------------------------------------------

    period_forecast = forecast_data.get(
        "period_forecast"
    )

    if period_forecast:

        period_fields = [
            "temperature_min",
            "temperature_max",
            "precipitation_probability_max",
            "precipitation_sum",
            "rain_sum",
            "wind_speed_max"
        ]

        for field in period_fields:

            value = period_forecast.get(
                field
            )

            if value is not None:

                try:

                    verified_values.append(
                        float(value)
                    )

                except (TypeError, ValueError):

                    continue

        # --------------------------------------------------
        # HOURLY PERIOD VALUES
        # --------------------------------------------------

        hours = period_forecast.get(
            "hours",
            []
        )

        for hour in hours:

            hourly_fields = [
                "temperature",
                "precipitation_probability",
                "precipitation",
                "rain",
                "wind_speed",
                "humidity",
                "cloud_cover"
            ]

            for field in hourly_fields:

                value = hour.get(
                    field
                )

                if value is not None:

                    try:

                        verified_values.append(
                            float(value)
                        )

                    except (TypeError, ValueError):

                        continue

    # --------------------------------------------------
    # NO VERIFIED VALUES
    # --------------------------------------------------

    if not verified_values:

        return {
            "safe": False,
            "reason": "Forecast data is empty."
        }

    # --------------------------------------------------
    # COMPARE RESPONSE NUMBERS
    # --------------------------------------------------

    # Every number in the response must be backed by the data.
    unsupported = find_unsupported_numbers(
        response_numbers,
        verified_values
    )

    if unsupported:

        return {
            "safe": False,
            "reason": (
                "Response contains numbers that are not "
                "in the verified forecast data: "
                + ", ".join(str(n) for n in unsupported)
            )
        }

    return {
        "safe": True,
        "reason": (
            "Response is supported by "
            "verified forecast data."
        )
    }


# --------------------------------------------------
# TEST HALLUCINATION CHECKS
# --------------------------------------------------

if __name__ == "__main__":

    # --------------------------------------------------
    # CURRENT WEATHER TEST
    # --------------------------------------------------

    weather_data = {
        "temperature": 24.1,
        "humidity": 80,
        "feels_like": 27.1,
        "precipitation": 0.0,
        "rain": 0.0,
        "wind_speed": 7.5
    }

    good_response = (
        "Current temperature is 24.1°C "
        "with humidity of 80%."
    )

    bad_response = (
        "Current temperature is 40°C "
        "and there is heavy rain."
    )

    print(
        "\n--- GOOD CURRENT WEATHER RESPONSE ---"
    )

    print(
        check_current_weather_response(
            good_response,
            weather_data
        )
    )

    print(
        "\n--- BAD CURRENT WEATHER RESPONSE ---"
    )

    print(
        check_current_weather_response(
            bad_response,
            weather_data
        )
    )

    # --------------------------------------------------
    # DAILY FORECAST TEST
    # --------------------------------------------------

    forecast_data = {

        "forecast": [

            {
                "date": "2026-09-29",
                "temperature_max": 30.7,
                "temperature_min": 21.9,
                "precipitation_probability": 7,
                "precipitation": 0.4,
                "wind_speed_max": 10.0
            }

        ]
    }

    good_forecast_response = (
        "Tomorrow's temperature will be "
        "21.9°C to 30.7°C with a "
        "7% chance of rain."
    )

    bad_forecast_response = (
        "Tomorrow there is a "
        "95% chance of heavy rain."
    )

    print(
        "\n--- GOOD DAILY FORECAST RESPONSE ---"
    )

    print(
        check_forecast_response(
            good_forecast_response,
            forecast_data
        )
    )

    print(
        "\n--- BAD DAILY FORECAST RESPONSE ---"
    )

    print(
        check_forecast_response(
            bad_forecast_response,
            forecast_data
        )
    )

    # --------------------------------------------------
    # PERIOD FORECAST TEST
    # --------------------------------------------------

    period_forecast_data = {

        "forecast": [],

        "period_forecast": {

            "date": "2026-09-30",

            "time_range": "evening",

            "temperature_min": 26.4,

            "temperature_max": 29.3,

            "precipitation_probability_max": 8,

            "precipitation_sum": 0.0,

            "rain_sum": 0.0,

            "wind_speed_max": 7.8,

            "status": "available",

            "hours": [

                {
                    "time": "2026-09-30T17:00",
                    "temperature": 29.3,
                    "precipitation_probability": 8,
                    "precipitation": 0.0,
                    "rain": 0.0,
                    "weather_code": 0,
                    "wind_speed": 7.8,
                    "humidity": 50,
                    "cloud_cover": 8
                },

                {
                    "time": "2026-09-30T18:00",
                    "temperature": 28.0,
                    "precipitation_probability": 6,
                    "precipitation": 0.0,
                    "rain": 0.0,
                    "weather_code": 0,
                    "wind_speed": 6.3,
                    "humidity": 60,
                    "cloud_cover": 5
                }

            ]
        }
    }

    good_period_response = (
        "Tomorrow evening in Mumbai, "
        "the temperature is expected to be "
        "26.4°C to 29.3°C with a maximum "
        "rain probability of 8%. "
        "Expected precipitation is 0 mm."
    )

    bad_period_response = (
        "Tomorrow evening there is a "
        "95% chance of heavy rain."
    )

    print(
        "\n--- GOOD PERIOD FORECAST RESPONSE ---"
    )

    print(
        check_forecast_response(
            good_period_response,
            period_forecast_data
        )
    )

    print(
        "\n--- BAD PERIOD FORECAST RESPONSE ---"
    )

    print(
        check_forecast_response(
            bad_period_response,
            period_forecast_data
        )
    )