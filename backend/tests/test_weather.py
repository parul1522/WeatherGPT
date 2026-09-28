WEATHER_HOST = "api.open-meteo.com"
BHOPAL = {"latitude": 23.2599, "longitude": 77.4126, "location_name": "Bhopal"}


def test_current_weather_is_normalized(client, mock_apis):
    response = client.get("/api/v1/weather/current", params=BHOPAL)
    assert response.status_code == 200
    body = response.json()

    assert body["location"] == {
        "name": "Bhopal", "latitude": 23.2599, "longitude": 77.4126, "country": None, "state": None,
    }
    assert body["current"] == {
        "temperature": 28.0,
        "feels_like": 31.2,
        "humidity": 72,
        "wind_speed": 18.0,
        "wind_direction": 240,
        "precipitation": 0.0,
        "weather_code": 2,
        "weather_description": "Partly cloudy",
    }
    assert body["units"]["temperature"] == "°C"
    assert body["source"] == "Open-Meteo"
    # 23:30 IST == 18:00 UTC
    assert body["updated_at"].startswith("2026-09-28T18:00:00")
    # Provider-specific fields are not leaked
    assert "temperature_2m" not in response.text and "interval" not in body["current"]


def test_current_weather_is_cached_in_memory(client, mock_apis):
    client.get("/api/v1/weather/current", params=BHOPAL)
    client.get("/api/v1/weather/current", params=BHOPAL)
    assert mock_apis.count(WEATHER_HOST) == 1


def test_current_weather_falls_back_to_recent_database_row(client, mock_apis):
    client.get("/api/v1/weather/current", params=BHOPAL)
    client.portal.call(client.app.state.cache.clear)  # simulate a restart / other worker
    response = client.get("/api/v1/weather/current", params=BHOPAL)
    assert response.status_code == 200
    assert response.json()["current"]["temperature"] == 28.0
    assert mock_apis.count(WEATHER_HOST) == 1


def test_current_weather_by_place_name(client, mock_apis):
    response = client.get("/api/v1/weather/current", params={"query": "Bhopal"})
    assert response.status_code == 200
    location = response.json()["location"]
    assert location["name"] == "Bhopal"
    assert location["state"] == "Madhya Pradesh"


def test_invalid_latitude_returns_400(client, mock_apis):
    response = client.get("/api/v1/weather/current", params={"latitude": 95, "longitude": 77})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_COORDINATES"
    assert mock_apis.count(WEATHER_HOST) == 0


def test_invalid_longitude_returns_400(client):
    response = client.get("/api/v1/weather/forecast", params={"latitude": 23, "longitude": -181})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_COORDINATES"


def test_latitude_without_longitude_returns_400(client):
    response = client.get("/api/v1/weather/current", params={"latitude": 23})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_COORDINATES"


def test_missing_location_returns_400(client):
    response = client.get("/api/v1/weather/current")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LOCATION_REQUIRED"


def test_forecast_returns_daily_and_hourly(client):
    response = client.get("/api/v1/weather/forecast", params={**BHOPAL, "days": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["days"] == 3
    assert body["timezone"] == "Asia/Kolkata"
    assert len(body["daily"]) == 3
    assert len(body["hourly"]) == 72
    first_day = body["daily"][0]
    assert first_day["date"] == "2026-09-28"
    assert first_day["weather_description"] == "Slight rain"
    assert first_day["precipitation_probability_max"] == 80
    assert first_day["sunrise"] == "2026-09-28T06:10:00+05:30"
    assert body["hourly"][0]["time"] == "2026-09-28T00:00:00+05:30"


def test_forecast_without_hourly(client):
    response = client.get("/api/v1/weather/forecast", params={**BHOPAL, "days": 7, "include_hourly": False})
    assert response.status_code == 200
    assert len(response.json()["daily"]) == 7
    assert response.json()["hourly"] == []


def test_forecast_days_out_of_range_returns_400(client):
    for days in (0, 8):
        response = client.get("/api/v1/weather/forecast", params={**BHOPAL, "days": days})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_weather_provider_failure_returns_502(client, mock_apis):
    mock_apis.fail_hosts[WEATHER_HOST] = 500
    response = client.get("/api/v1/weather/current", params=BHOPAL)
    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "WEATHER_PROVIDER_UNAVAILABLE"
    assert "Traceback" not in response.text and "mock failure" not in response.text


def test_weather_provider_timeout_returns_502(client, mock_apis):
    mock_apis.timeout_hosts.add(WEATHER_HOST)
    response = client.get("/api/v1/weather/forecast", params=BHOPAL)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "WEATHER_PROVIDER_UNAVAILABLE"
    assert "timed out" in response.json()["error"]["message"]


def test_weather_provider_missing_fields_returns_502(client, mock_apis):
    mock_apis.current_override = {"utc_offset_seconds": 0, "current": {"time": "2026-09-28T12:00"}}
    response = client.get("/api/v1/weather/current", params=BHOPAL)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "WEATHER_PROVIDER_UNAVAILABLE"


def test_weather_provider_optional_fields_can_be_missing(client, mock_apis):
    payload = {"utc_offset_seconds": 0, "current": {"time": "2026-09-28T12:00", "temperature_2m": 30}}
    mock_apis.current_override = payload
    response = client.get("/api/v1/weather/current", params=BHOPAL)
    assert response.status_code == 200
    assert response.json()["current"]["humidity"] is None


def test_weather_provider_non_json_returns_502(client, mock_apis):
    mock_apis.html_hosts.add(WEATHER_HOST)
    response = client.get("/api/v1/weather/current", params=BHOPAL)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "WEATHER_PROVIDER_UNAVAILABLE"
