import datetime as dt

import pytest

from app.api.deps import get_settings
from app.core.config import Settings
from app.services.cache import InMemoryTTLCache

BHOPAL = {"latitude": 23.2599, "longitude": 77.4126}


# ---------- location ----------

def test_geocode_returns_location(client):
    response = client.get("/api/v1/location/geocode", params={"query": "Bhopal"})
    assert response.status_code == 200
    assert response.json() == {
        "name": "Bhopal",
        "latitude": 23.2547,
        "longitude": 77.4029,
        "country": "India",
        "state": "Madhya Pradesh",
    }


def test_geocode_uses_state_qualifier(client):
    response = client.get("/api/v1/location/geocode", params={"query": "Aurangabad, Bihar"})
    assert response.status_code == 200
    assert response.json()["state"] == "Bihar"


def test_geocode_results_are_cached(client, mock_apis):
    client.get("/api/v1/location/geocode", params={"query": "Bhopal"})
    client.get("/api/v1/location/geocode", params={"query": "  bhopal "})
    assert mock_apis.count("geocoding-api.open-meteo.com") == 1


def test_geocode_unknown_place_returns_404(client):
    response = client.get("/api/v1/location/geocode", params={"query": "Atlantis"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LOCATION_NOT_FOUND"


def test_geocode_provider_failure_returns_502(client, mock_apis):
    mock_apis.fail_hosts["geocoding-api.open-meteo.com"] = 500
    response = client.get("/api/v1/location/geocode", params={"query": "Bhopal"})
    assert response.status_code == 502


# ---------- alerts ----------

def test_alerts_without_provider_matches_contract(client):
    response = client.get("/api/v1/alerts", params=BHOPAL)
    assert response.status_code == 200
    body = response.json()
    assert body["alerts"] == []
    assert body["source"] is None
    assert body["message"] == "No alert provider configured."
    assert body["advisories"] == []


def test_advisories_are_labelled_unofficial(client, mock_apis):
    mock_apis.forecast_rain_mm = 120.0
    response = client.get("/api/v1/alerts", params={**BHOPAL, "include_advisories": True})
    assert response.status_code == 200
    body = response.json()
    assert body["alerts"] == []
    assert len(body["advisories"]) == 3  # one per forecast day
    advisory = body["advisories"][0]
    assert advisory["advisory_type"] == "heavy_rain"
    assert advisory["level"] == "high"
    assert advisory["is_official"] is False
    assert "Not an official warning" in advisory["basis"]


def test_no_advisories_for_normal_weather(client):
    response = client.get("/api/v1/alerts", params={**BHOPAL, "include_advisories": True})
    assert response.json()["advisories"] == []


# ---------- climate ----------

def test_climate_history_with_monthly_breakdown(client):
    response = client.get(
        "/api/v1/climate/history", params={**BHOPAL, "start_date": "2025-06-29", "end_date": "2025-07-02"}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["daily"]) == 4
    assert [m["month"] for m in body["monthly"]] == ["2025-06", "2025-07"]
    assert body["summary"]["precipitation_total"] == 20.0
    assert body["summary"]["rainy_days"] == 2
    assert body["summary"]["temperature_mean"] == 27.0
    assert body["source"] == "Open-Meteo Historical"


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2025-07-02", "2025-06-01"),  # reversed
        ("2020-01-01", "2025-01-01"),  # too long
        ("1900-01-01", "1900-01-05"),  # too early
        ((dt.date.today() - dt.timedelta(days=2)).isoformat(), (dt.date.today() + dt.timedelta(days=1)).isoformat()),
        ("2025-13-01", "2025-12-31"),  # not a date
    ],
)
def test_climate_history_rejects_bad_dates(client, start, end):
    response = client.get("/api/v1/climate/history", params={**BHOPAL, "start_date": start, "end_date": end})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"


# ---------- security ----------

def test_api_key_is_enforced_when_configured(client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(API_KEY="secret-key-123")
    assert client.get("/api/v1/alerts", params=BHOPAL).status_code == 401
    assert client.get("/api/v1/alerts", params=BHOPAL, headers={"X-API-Key": "wrong"}).status_code == 401
    ok = client.get("/api/v1/alerts", params=BHOPAL, headers={"X-API-Key": "secret-key-123"})
    assert ok.status_code == 200
    assert client.get("/health").status_code == 200  # health stays public


# ---------- cache ----------

async def test_ttl_cache_expires_entries(monkeypatch):
    cache = InMemoryTTLCache(max_items=2)
    now = [1000.0]
    monkeypatch.setattr("app.services.cache.time.monotonic", lambda: now[0])

    await cache.set("a", 1, ttl_seconds=10)
    assert await cache.get("a") == 1
    now[0] += 11
    assert await cache.get("a") is None

    await cache.set("zero", 1, ttl_seconds=0)
    assert await cache.get("zero") is None

    await cache.set("b", 2, 10)
    await cache.set("c", 3, 10)
    await cache.set("d", 4, 10)  # evicts the oldest
    assert await cache.get("b") is None
    assert await cache.get("d") == 4
