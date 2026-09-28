from app.api.deps import get_settings
from app.core.config import Settings

GROQ_HOST = "api.groq.com"
GEMINI_HOST = "generativelanguage.googleapis.com"


def test_chat_answers_from_verified_forecast(client, mock_apis):
    response = client.post("/api/v1/chat", json={"message": "Will it rain tomorrow in Bhopal?", "language": "en"})
    assert response.status_code == 200
    body = response.json()

    assert body["answer"] == mock_apis.answer
    assert body["language"] == "en"
    assert body["intent"] == "forecast"
    assert body["location"]["name"] == "Bhopal"
    assert body["data_used"] == {"weather": False, "forecast": True, "alerts": False}
    assert body["sources"] == ["Open-Meteo"]
    assert body["generated_at"]

    # Two Groq calls: intent extraction (JSON mode), then the answer containing the real forecast.
    intent_call, answer_call = mock_apis.ai_bodies()
    assert intent_call["response_format"] == {"type": "json_object"}
    assert intent_call["model"] == "openai/gpt-oss-20b"
    assert intent_call["reasoning_effort"] == "low" and intent_call["include_reasoning"] is False
    assert "response_format" not in answer_call
    data = mock_apis.answer_prompt_data()
    assert data["forecast"]["daily"][1]["precipitation_sum"] == 3.2
    # Only tomorrow's hourly rows are sent to keep the prompt small.
    assert {h["time"][:10] for h in data["forecast"]["hourly"]} == {"2026-09-29"}


def test_chat_uses_device_coordinates_when_no_place_named(client, mock_apis):
    mock_apis.intent = {"intent": "current_weather", "location": None, "time_range": "now"}
    response = client.post(
        "/api/v1/chat",
        json={"message": "How hot is it here?", "latitude": 23.2599, "longitude": 77.4126, "location_name": "Bhopal"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["location"]["latitude"] == 23.2599
    assert body["data_used"]["weather"] is True
    assert mock_apis.count("geocoding-api.open-meteo.com") == 0


def test_chat_general_question_fetches_no_weather(client, mock_apis):
    mock_apis.intent = {"intent": "general", "location": None, "time_range": None}
    response = client.post("/api/v1/chat", json={"message": "What does humidity mean?"})
    assert response.status_code == 200
    assert response.json()["location"] is None
    assert response.json()["sources"] == []
    assert mock_apis.count("api.open-meteo.com") == 0


def test_chat_alert_question_never_claims_official_alerts(client, mock_apis):
    mock_apis.intent = {"intent": "alerts", "location": "Bhopal", "time_range": None}
    mock_apis.forecast_rain_mm = 80.0
    response = client.post("/api/v1/chat", json={"message": "Any storm warnings for Bhopal?"})
    assert response.status_code == 200
    assert response.json()["data_used"]["alerts"] is True

    data = mock_apis.answer_prompt_data()
    assert data["official_alerts"] == []
    assert data["official_alert_status"] == "No alert provider configured."
    assert data["app_advisories"][0]["is_official"] is False


def test_chat_normalizes_inconsistent_intent_flags(client, mock_apis):
    # LLM says "forecast" but forgets the flag; the backend still fetches the forecast.
    mock_apis.intent = {"intent": "forecast", "location": "Bhopal", "requires_forecast": False}
    response = client.post("/api/v1/chat", json={"message": "Forecast for Bhopal"})
    assert response.status_code == 200
    assert response.json()["data_used"]["forecast"] is True


def test_chat_rejects_empty_message(client, mock_apis):
    for message in ("", "   "):
        response = client.post("/api/v1/chat", json={"message": message})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert mock_apis.count(GROQ_HOST) == 0


def test_chat_rejects_missing_message_and_long_message(client):
    assert client.post("/api/v1/chat", json={}).status_code == 400
    assert client.post("/api/v1/chat", json={"message": "x" * 1001}).status_code == 400


def test_chat_rejects_invalid_coordinates(client):
    response = client.post("/api/v1/chat", json={"message": "weather?", "latitude": 100, "longitude": 77})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_COORDINATES"

    response = client.post("/api/v1/chat", json={"message": "weather?", "latitude": 23})
    assert response.status_code == 400


def test_chat_rejects_invalid_language(client):
    response = client.post("/api/v1/chat", json={"message": "weather?", "language": "English!"})
    assert response.status_code == 400


def test_chat_requires_location_when_data_needed(client, mock_apis):
    mock_apis.intent = {"intent": "current_weather", "location": None}
    response = client.post("/api/v1/chat", json={"message": "Is it hot?"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LOCATION_REQUIRED"


def test_chat_unknown_place_returns_404(client, mock_apis):
    mock_apis.intent = {"intent": "current_weather", "location": "Atlantis"}
    response = client.post("/api/v1/chat", json={"message": "Weather in Atlantis?"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LOCATION_NOT_FOUND"


def test_ai_service_failure_returns_503(client, mock_apis):
    mock_apis.fail_hosts[GROQ_HOST] = 500
    response = client.post("/api/v1/chat", json={"message": "Will it rain tomorrow in Bhopal?"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_SERVICE_UNAVAILABLE"
    assert mock_apis.count("api.open-meteo.com") == 0


def test_ai_service_timeout_returns_503(client, mock_apis):
    mock_apis.timeout_hosts.add(GROQ_HOST)
    response = client.post("/api/v1/chat", json={"message": "Will it rain tomorrow in Bhopal?"})
    assert response.status_code == 503


def test_ai_invalid_intent_json_returns_502(client, mock_apis):
    mock_apis.intent = "it will probably rain"  # not JSON
    response = client.post("/api/v1/chat", json={"message": "Will it rain tomorrow in Bhopal?"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "AI_INVALID_RESPONSE"


def test_ai_intent_with_unknown_values_is_rejected(client, mock_apis):
    mock_apis.intent = {"intent": "make_it_rain", "location": "Bhopal"}
    response = client.post("/api/v1/chat", json={"message": "Will it rain tomorrow in Bhopal?"})
    assert response.status_code == 502


def test_ai_not_configured_returns_503(client, mock_apis):
    client.app.dependency_overrides[get_settings] = lambda: Settings(AI_PROVIDER="none")
    response = client.post("/api/v1/chat", json={"message": "Will it rain tomorrow in Bhopal?"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_SERVICE_NOT_CONFIGURED"


def test_ai_rate_limit_returns_503_with_message(client, mock_apis):
    mock_apis.fail_hosts[GROQ_HOST] = 429
    response = client.post("/api/v1/chat", json={"message": "Will it rain tomorrow in Bhopal?"})
    assert response.status_code == 503
    assert "rate limit" in response.json()["error"]["message"]


def test_groq_non_reasoning_model_gets_no_reasoning_options(client, mock_apis):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        GROQ_API_KEY="gsk-test", GROQ_MODEL="llama-3.3-70b-versatile"
    )
    assert client.post("/api/v1/chat", json={"message": "Rain in Bhopal tomorrow?"}).status_code == 200
    body = mock_apis.ai_bodies()[0]
    assert body["model"] == "llama-3.3-70b-versatile"
    assert "reasoning_effort" not in body and "include_reasoning" not in body


def test_groq_key_can_come_from_llm_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "gsk-from-root-env")
    assert Settings().GROQ_API_KEY.get_secret_value() == "gsk-from-root-env"


def test_openai_provider_can_replace_groq(client, mock_apis):
    client.app.dependency_overrides[get_settings] = lambda: Settings(AI_PROVIDER="openai", OPENAI_API_KEY="sk-test")
    response = client.post("/api/v1/chat", json={"message": "Will it rain tomorrow in Bhopal?"})
    assert response.status_code == 200
    assert response.json()["answer"] == mock_apis.answer
    assert mock_apis.count("api.openai.com") == 2
    assert mock_apis.count(GROQ_HOST) == 0


def test_gemini_provider_can_replace_groq(client, mock_apis):
    client.app.dependency_overrides[get_settings] = lambda: Settings(AI_PROVIDER="gemini", GEMINI_API_KEY="g-test")
    response = client.post("/api/v1/chat", json={"message": "Will it rain tomorrow in Bhopal?"})
    assert response.status_code == 200
    assert mock_apis.count(GEMINI_HOST) == 2
    assert mock_apis.answer_prompt_data(GEMINI_HOST)["forecast"]["daily"][1]["precipitation_sum"] == 3.2


def test_weather_failure_during_chat_returns_502(client, mock_apis):
    mock_apis.fail_hosts["api.open-meteo.com"] = 503
    response = client.post("/api/v1/chat", json={"message": "Will it rain tomorrow in Bhopal?"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "WEATHER_PROVIDER_UNAVAILABLE"
    # The answer step must not run without verified data.
    assert len(mock_apis.ai_bodies()) == 1
