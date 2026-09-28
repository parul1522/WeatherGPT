"""Shared test setup.

Every external API (Open-Meteo, geocoding, archive, Gemini) is served by `MockAPIs` through an
httpx.MockTransport, so tests never touch the network. The database is a throwaway SQLite file.
"""

import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any

# Configure the app for tests *before* importing it (settings are read once at import time).
_TMP_DIR = Path(tempfile.mkdtemp(prefix="weathergpt-tests-"))
DB_PATH = _TMP_DIR / "test.db"
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{DB_PATH}",
        "AI_PROVIDER": "groq",
        "GROQ_API_KEY": "test-groq-key",
        "GEMINI_API_KEY": "",
        "OPENAI_API_KEY": "",
        "API_KEY": "",
        "ALERT_PROVIDER": "none",
        "LOG_LEVEL": "WARNING",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import get_http_client  # noqa: E402
from app.main import app  # noqa: E402

BASE_DATE = dt.date(2026, 9, 28)

GEOCODE_RESULTS: dict[str, list[dict[str, Any]]] = {
    "bhopal": [
        {"name": "Bhopal", "latitude": 23.25469, "longitude": 77.40289, "country": "India",
         "country_code": "IN", "admin1": "Madhya Pradesh"},
    ],
    "aurangabad": [
        {"name": "Aurangabad", "latitude": 19.87757, "longitude": 75.34226, "country": "India",
         "country_code": "IN", "admin1": "Maharashtra"},
        {"name": "Aurangabad", "latitude": 24.75204, "longitude": 84.3742, "country": "India",
         "country_code": "IN", "admin1": "Bihar"},
    ],
}


def current_payload(**overrides: Any) -> dict[str, Any]:
    current = {
        "time": "2026-09-28T23:30",
        "interval": 900,
        "temperature_2m": 28.04,
        "apparent_temperature": 31.2,
        "relative_humidity_2m": 72,
        "precipitation": 0.0,
        "weather_code": 2,
        "wind_speed_10m": 18.0,
        "wind_direction_10m": 240,
    }
    current.update(overrides)
    return {"latitude": 23.25, "longitude": 77.41, "utc_offset_seconds": 19800,
            "timezone": "Asia/Kolkata", "current": current}


def forecast_payload(days: int, *, hourly: bool, rain_mm: float = 3.2) -> dict[str, Any]:
    dates = [(BASE_DATE + dt.timedelta(days=i)).isoformat() for i in range(days)]
    payload: dict[str, Any] = {
        "latitude": 23.25,
        "longitude": 77.41,
        "utc_offset_seconds": 19800,
        "timezone": "Asia/Kolkata",
        "daily": {
            "time": dates,
            "weather_code": [61] * days,
            "temperature_2m_max": [31.5] * days,
            "temperature_2m_min": [22.1] * days,
            "precipitation_sum": [rain_mm] * days,
            "precipitation_probability_max": [80] * days,
            "wind_speed_10m_max": [14.0] * days,
            "sunrise": [f"{d}T06:10" for d in dates],
            "sunset": [f"{d}T18:05" for d in dates],
        },
    }
    if hourly:
        times = [f"{d}T{h:02d}:00" for d in dates for h in range(24)]
        payload["hourly"] = {
            "time": times,
            "temperature_2m": [25.0] * len(times),
            "relative_humidity_2m": [80] * len(times),
            "precipitation": [0.2] * len(times),
            "precipitation_probability": [60] * len(times),
            "weather_code": [61] * len(times),
            "wind_speed_10m": [10.0] * len(times),
        }
    return payload


def archive_payload(start: str, end: str) -> dict[str, Any]:
    first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    dates = [(first + dt.timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
    # Alternate rainy (10 mm) and dry (0 mm) days so aggregates are easy to check.
    return {
        "utc_offset_seconds": 19800,
        "daily": {
            "time": dates,
            "temperature_2m_max": [32.0] * len(dates),
            "temperature_2m_min": [22.0] * len(dates),
            "temperature_2m_mean": [27.0] * len(dates),
            "precipitation_sum": [10.0 if i % 2 == 0 else 0.0 for i in range(len(dates))],
            "wind_speed_10m_max": [12.0] * len(dates),
        },
    }


def gemini_payload(text: str) -> dict[str, Any]:
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]}


class MockAPIs:
    """Programmable fake for all external APIs. Tests change attributes to simulate failures."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.current_override: dict[str, Any] | None = None
        self.forecast_rain_mm = 3.2
        self.fail_hosts: dict[str, int] = {}  # host -> HTTP status to return
        self.timeout_hosts: set[str] = set()
        self.html_hosts: set[str] = set()  # hosts that answer 200 with a non-JSON body
        self.intent: Any = {
            "intent": "forecast",
            "location": "Bhopal",
            "time_range": "tomorrow",
            "requires_current_weather": False,
            "requires_forecast": True,
            "requires_alerts": False,
        }
        self.answer = "Yes, light rain is likely in Bhopal tomorrow with about 3.2 mm expected."

    def count(self, host: str) -> int:
        return sum(1 for r in self.requests if r.url.host == host)

    def ai_bodies(self, host: str = "api.groq.com") -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests if r.url.host == host]

    def answer_prompt_data(self, host: str = "api.groq.com") -> dict[str, Any]:
        """The VERIFIED DATA JSON sent to the LLM in the answer-generation call."""
        body = self.ai_bodies(host)[1]
        prompt = body["messages"][1]["content"] if "messages" in body else body["contents"][0]["parts"][0]["text"]
        return json.loads(prompt.split("VERIFIED DATA (JSON):\n", 1)[1])

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host, params = request.url.host, request.url.params

        if host in self.timeout_hosts:
            raise httpx.ReadTimeout("timed out", request=request)
        if host in self.fail_hosts:
            return httpx.Response(self.fail_hosts[host], json={"error": True, "reason": "mock failure"})
        if host in self.html_hosts:
            return httpx.Response(200, text="<html>maintenance</html>")

        if host == "api.open-meteo.com":
            if "current" in params:
                return httpx.Response(200, json=self.current_override or current_payload())
            return httpx.Response(
                200,
                json=forecast_payload(int(params["forecast_days"]), hourly="hourly" in params,
                                      rain_mm=self.forecast_rain_mm),
            )
        if host == "geocoding-api.open-meteo.com":
            results = GEOCODE_RESULTS.get(params["name"].lower())
            return httpx.Response(200, json={"results": results} if results else {"generationtime_ms": 0.1})
        if host == "archive-api.open-meteo.com":
            return httpx.Response(200, json=archive_payload(params["start_date"], params["end_date"]))
        if host == "generativelanguage.googleapis.com":
            body = json.loads(request.content)
            if body["generationConfig"].get("responseMimeType") == "application/json":
                text = self.intent if isinstance(self.intent, str) else json.dumps(self.intent)
                return httpx.Response(200, json=gemini_payload(text))
            return httpx.Response(200, json=gemini_payload(self.answer))
        if host in ("api.groq.com", "api.openai.com"):
            body = json.loads(request.content)
            if body.get("response_format", {}).get("type") == "json_object":
                text = self.intent if isinstance(self.intent, str) else json.dumps(self.intent)
            else:
                text = self.answer
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": text}}]})
        return httpx.Response(404, json={"error": "unknown host in test"})


@pytest.fixture
def mock_apis() -> MockAPIs:
    return MockAPIs()


@pytest.fixture
def client(mock_apis: MockAPIs):
    DB_PATH.unlink(missing_ok=True)  # fresh database per test; tables are created on startup
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_apis))
    app.dependency_overrides[get_http_client] = lambda: http_client
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
