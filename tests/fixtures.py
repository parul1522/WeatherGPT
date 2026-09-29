"""Deterministic Open-Meteo / IMD fixtures used to test WeatherGPT offline.

Nothing here talks to the network. ``FakeRequests`` replaces ``requests.get``
so the real tools, validation, hallucination checks and translation all run.
"""

from datetime import datetime, timedelta

import requests

# Per-city marker values so tests can prove the *right* city's data was used.
CITY_BY_LAT = {
    23.2599: {"name": "Bhopal", "temp": 30.0, "prob": 80, "wind": 12.0},
    19.076: {"name": "Mumbai", "temp": 33.0, "prob": 15, "wind": 20.0},
    28.6139: {"name": "Delhi", "temp": 36.0, "prob": 5, "wind": 8.0},
    18.5204: {"name": "Pune", "temp": 27.0, "prob": 40, "wind": 31.0},
}


def _city(params):
    lat = round(float(params["latitude"]), 4)
    for key, value in CITY_BY_LAT.items():
        if abs(key - lat) < 0.001:
            return value
    return {"name": "Other", "temp": 25.0, "prob": 10, "wind": 5.0}


def current_payload(params):
    city = _city(params)
    return {
        "current": {
            "time": datetime.now().strftime("%Y-%m-%dT%H:00"),
            "temperature_2m": city["temp"],
            "relative_humidity_2m": 55,
            "apparent_temperature": city["temp"] + 1.5,
            "precipitation": 0.0,
            "rain": 0.0,
            "weather_code": 1,
            "cloud_cover": 20,
            "wind_speed_10m": city["wind"],
            "wind_direction_10m": 180,
        }
    }


def forecast_payload(params):
    city = _city(params)
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    hourly = {k: [] for k in (
        "time", "temperature_2m", "precipitation_probability", "precipitation",
        "rain", "weather_code", "wind_speed_10m", "relative_humidity_2m",
        "cloud_cover")}
    daily = {k: [] for k in (
        "time", "temperature_2m_max", "temperature_2m_min",
        "precipitation_probability_max", "precipitation_sum", "weather_code",
        "wind_speed_10m_max")}
    for day in range(7):
        date = start + timedelta(days=day)
        daily["time"].append(date.strftime("%Y-%m-%d"))
        daily["temperature_2m_max"].append(city["temp"] + 4)
        daily["temperature_2m_min"].append(city["temp"] - 6)
        daily["precipitation_probability_max"].append(city["prob"])
        daily["precipitation_sum"].append(2.4)
        daily["weather_code"].append(61)
        daily["wind_speed_10m_max"].append(city["wind"] + 3)
        for hour in range(24):
            stamp = date + timedelta(hours=hour)
            hourly["time"].append(stamp.strftime("%Y-%m-%dT%H:00"))
            hourly["temperature_2m"].append(round(city["temp"] - 6 + hour * 0.4, 1))
            hourly["precipitation_probability"].append(city["prob"])
            hourly["precipitation"].append(0.2)
            hourly["rain"].append(0.2)
            hourly["weather_code"].append(61)
            hourly["wind_speed_10m"].append(city["wind"])
            hourly["relative_humidity_2m"].append(70)
            hourly["cloud_cover"].append(60)
    return {"timezone": "Asia/Kolkata", "hourly": hourly, "daily": daily}


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeRequests:
    """Callable replacement for ``requests.get`` that records every call."""

    def __init__(self, fail=False, imd_payload=None, imd_fail=False):
        self.fail, self.imd_payload, self.imd_fail = fail, imd_payload, imd_fail
        self.calls = []

    def __call__(self, url, params=None, timeout=None, **kwargs):
        self.calls.append((url, dict(params or {})))
        if "mausam.imd.gov.in" in url:
            if self.imd_fail:
                raise requests.ConnectionError("IMD down (test)")
            return FakeResponse(self.imd_payload)
        if self.fail:
            raise requests.ConnectionError("network down (test)")
        if "archive-api" in url:
            return FakeResponse({
                "timezone": "Asia/Kolkata",
                "daily": {"time": ["2025-09-01"], "temperature_2m_mean": [27.0],
                          "temperature_2m_max": [31.0], "temperature_2m_min": [23.0],
                          "precipitation_sum": [4.0], "rain_sum": [4.0]}})
        if "current" in (params or {}):
            return FakeResponse(current_payload(params))
        return FakeResponse(forecast_payload(params))
