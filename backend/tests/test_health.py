def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "WeatherGPT API"}


def test_docs_and_openapi_are_available(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/health",
        "/api/v1/weather/current",
        "/api/v1/weather/forecast",
        "/api/v1/chat",
        "/api/v1/alerts",
        "/api/v1/climate/history",
        "/api/v1/location/geocode",
    ):
        assert path in paths


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
