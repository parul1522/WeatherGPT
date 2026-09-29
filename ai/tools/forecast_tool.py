import requests
from datetime import datetime, timedelta


def get_time_range_hours(time_range: str) -> tuple:
    """
    Return the start and end hour for a requested
    time range.

    Returns:
        Tuple containing start hour and end hour.
    """

    time_ranges = {
        "morning": (6, 11),
        "afternoon": (12, 16),
        "evening": (17, 20),
        "night": (21, 23),
        "full_day": (0, 23)
    }

    return time_ranges.get(
        time_range,
        (0, 23)
    )


def extract_period_forecast(
    hourly: dict,
    date: str,
    time_range: str
) -> dict:
    """
    Extract forecast information for a specific
    date and time range from hourly forecast data.

    Args:
        hourly: Hourly Open-Meteo forecast data.
        date: Date in YYYY-MM-DD format.
        time_range: morning, afternoon, evening,
                    night, or full_day.

    Returns:
        Standardized period forecast dictionary.
    """

    times = hourly.get(
        "time",
        []
    )

    temperatures = hourly.get(
        "temperature_2m",
        []
    )

    precipitation_probabilities = hourly.get(
        "precipitation_probability",
        []
    )

    precipitation = hourly.get(
        "precipitation",
        []
    )

    rain = hourly.get(
        "rain",
        []
    )

    weather_codes = hourly.get(
        "weather_code",
        []
    )

    wind_speeds = hourly.get(
        "wind_speed_10m",
        []
    )

    humidity = hourly.get(
        "relative_humidity_2m",
        []
    )

    cloud_cover = hourly.get(
        "cloud_cover",
        []
    )

    start_hour, end_hour = get_time_range_hours(
        time_range
    )

    selected = []

    for i, timestamp in enumerate(times):

        try:
            current_time = datetime.fromisoformat(
                timestamp
            )

        except ValueError:
            continue

        if current_time.strftime(
            "%Y-%m-%d"
        ) != date:
            continue

        if not (
            start_hour
            <= current_time.hour
            <= end_hour
        ):
            continue

        selected.append({
            "time": timestamp,
            "temperature": (
                temperatures[i]
                if i < len(temperatures)
                else None
            ),
            "precipitation_probability": (
                precipitation_probabilities[i]
                if i < len(precipitation_probabilities)
                else None
            ),
            "precipitation": (
                precipitation[i]
                if i < len(precipitation)
                else None
            ),
            "rain": (
                rain[i]
                if i < len(rain)
                else None
            ),
            "weather_code": (
                weather_codes[i]
                if i < len(weather_codes)
                else None
            ),
            "wind_speed": (
                wind_speeds[i]
                if i < len(wind_speeds)
                else None
            ),
            "humidity": (
                humidity[i]
                if i < len(humidity)
                else None
            ),
            "cloud_cover": (
                cloud_cover[i]
                if i < len(cloud_cover)
                else None
            )
        })

    if not selected:
        return {
            "date": date,
            "time_range": time_range,
            "hours": [],
            "temperature_min": None,
            "temperature_max": None,
            "precipitation_probability_max": None,
            "precipitation_sum": None,
            "rain_sum": None,
            "wind_speed_max": None,
            "status": "no_data"
        }

    # --------------------------------------------------
    # CALCULATE PERIOD SUMMARY
    # --------------------------------------------------

    valid_temperatures = [
        item["temperature"]
        for item in selected
        if item["temperature"] is not None
    ]

    valid_probabilities = [
        item["precipitation_probability"]
        for item in selected
        if item["precipitation_probability"]
        is not None
    ]

    valid_precipitation = [
        item["precipitation"]
        for item in selected
        if item["precipitation"] is not None
    ]

    valid_rain = [
        item["rain"]
        for item in selected
        if item["rain"] is not None
    ]

    valid_wind = [
        item["wind_speed"]
        for item in selected
        if item["wind_speed"] is not None
    ]

    return {
        "date": date,
        "time_range": time_range,
        "hours": selected,

        "temperature_min": (
            min(valid_temperatures)
            if valid_temperatures
            else None
        ),

        "temperature_max": (
            max(valid_temperatures)
            if valid_temperatures
            else None
        ),

        "precipitation_probability_max": (
            max(valid_probabilities)
            if valid_probabilities
            else None
        ),

        "precipitation_sum": (
            round(sum(valid_precipitation), 2)
            if valid_precipitation
            else None
        ),

        "rain_sum": (
            round(sum(valid_rain), 2)
            if valid_rain
            else None
        ),

        "wind_speed_max": (
            max(valid_wind)
            if valid_wind
            else None
        ),

        "status": "available"
    }


def get_forecast(
    latitude: float,
    longitude: float,
    days: int = 7,
    target_date: str = None,
    time_range: str = "full_day"
) -> dict:
    """
    Fetch weather forecast for a location.

    Args:
        latitude: Location latitude.
        longitude: Location longitude.
        days: Number of forecast days.
        target_date: Optional date in YYYY-MM-DD format.
        time_range: morning, afternoon, evening,
                    night, or full_day.

    Returns:
        A standardized forecast dictionary.
    """

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "forecast_days": days,
        "hourly": (
            "temperature_2m,"
            "precipitation_probability,"
            "precipitation,"
            "rain,"
            "weather_code,"
            "wind_speed_10m,"
            "relative_humidity_2m,"
            "cloud_cover"
        ),
        "daily": (
            "temperature_2m_max,"
            "temperature_2m_min,"
            "precipitation_probability_max,"
            "precipitation_sum,"
            "weather_code,"
            "wind_speed_10m_max"
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

        hourly = data.get(
            "hourly",
            {}
        )

        daily = data.get(
            "daily",
            {}
        )

        # --------------------------------------------------
        # DAILY FORECAST
        # --------------------------------------------------

        forecast = []

        dates = daily.get(
            "time",
            []
        )

        temperature_max = daily.get(
            "temperature_2m_max",
            []
        )

        temperature_min = daily.get(
            "temperature_2m_min",
            []
        )

        precipitation_probability_max = daily.get(
            "precipitation_probability_max",
            []
        )

        precipitation_sum = daily.get(
            "precipitation_sum",
            []
        )

        weather_codes = daily.get(
            "weather_code",
            []
        )

        wind_speed_max = daily.get(
            "wind_speed_10m_max",
            []
        )

        for i, date in enumerate(dates):

            forecast.append({
                "date": date,

                "temperature_max": (
                    temperature_max[i]
                    if i < len(temperature_max)
                    else None
                ),

                "temperature_min": (
                    temperature_min[i]
                    if i < len(temperature_min)
                    else None
                ),

                "precipitation_probability": (
                    precipitation_probability_max[i]
                    if i < len(
                        precipitation_probability_max
                    )
                    else None
                ),

                "precipitation": (
                    precipitation_sum[i]
                    if i < len(precipitation_sum)
                    else None
                ),

                "weather_code": (
                    weather_codes[i]
                    if i < len(weather_codes)
                    else None
                ),

                "wind_speed_max": (
                    wind_speed_max[i]
                    if i < len(wind_speed_max)
                    else None
                )
            })

        # --------------------------------------------------
        # TARGET DATE PERIOD FORECAST
        # --------------------------------------------------

        period_forecast = None

        if target_date:

            period_forecast = extract_period_forecast(
                hourly=hourly,
                date=target_date,
                time_range=time_range
            )

        # --------------------------------------------------
        # RETURN RESULT
        # --------------------------------------------------

        return {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": data.get(
                "timezone"
            ),

            "forecast": forecast,

            "period_forecast": period_forecast,

            "hourly": hourly,

            "source": "Open-Meteo"
        }

    except requests.RequestException as error:

        return {
            "error": "Unable to retrieve forecast data.",
            "details": str(error),
            "source": "Open-Meteo"
        }


# --------------------------------------------------
# TEST THE FORECAST TOOL
# --------------------------------------------------

if __name__ == "__main__":

    # Example:
    # Bhopal tomorrow evening

    tomorrow = (
        datetime.now()
        + timedelta(days=1)
    ).strftime(
        "%Y-%m-%d"
    )

    forecast = get_forecast(
        latitude=23.2599,
        longitude=77.4126,
        days=7,
        target_date=tomorrow,
        time_range="evening"
    )

    print("\n========================================")
    print("FORECAST TOOL TEST")
    print("========================================")

    print("\nTarget date:")
    print(tomorrow)

    print("\nTime range:")
    print("evening")

    print("\nPeriod forecast:")
    print(
        forecast.get(
            "period_forecast"
        )
    )