"""HTTP-level tests for the FastAPI backend.

These need the web stack (fastapi + httpx, see requirements.txt) and are
skipped when it is not installed.
"""

import os
import unittest
from unittest import mock

try:
    from fastapi.testclient import TestClient
    HAVE_FASTAPI = True
except ImportError:  # pragma: no cover
    HAVE_FASTAPI = False

from tests.fixtures import FakeRequests


@unittest.skipUnless(HAVE_FASTAPI, "fastapi/httpx not installed")
class TestBackendApi(unittest.TestCase):
    def setUp(self):
        from ai.agents import weather_agent as wa
        from backend.app.main import app
        from backend.app.services import ai_service

        ai_service.reset_sessions()
        self.client = TestClient(app)
        for p in (mock.patch("requests.get", FakeRequests()),
                  mock.patch.object(wa, "groq_client", None),
                  mock.patch.dict(os.environ, {"IMD_DISTRICT_IDS": ""})):
            p.start()
            self.addCleanup(p.stop)

    def test_health(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_chat_reaches_ai_pipeline_not_canned_reply(self):
        r = self.client.post("/api/chat", json={
            "message": "Will it rain tomorrow in Bhopal?"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("Forecast for Bhopal", body["reply"])
        self.assertNotIn("You asked", body["reply"])
        self.assertTrue(body["session_id"])

    def test_chat_followup_with_session_id(self):
        first = self.client.post("/api/chat", json={
            "message": "Will it rain tomorrow in Bhopal?"}).json()
        second = self.client.post("/api/chat", json={
            "message": "What about evening?",
            "session_id": first["session_id"]}).json()
        self.assertIn("Forecast for Bhopal", second["reply"])
        self.assertIn("Time period: evening", second["reply"])

    def test_chat_hindi(self):
        body = self.client.post("/api/chat", json={
            "message": "कल भोपाल में बारिश होगी क्या?"}).json()
        self.assertEqual(body["lang"], "hi")

    def test_chat_pipeline_failure_is_503(self):
        from backend.app.services import ai_service
        with mock.patch.object(ai_service, "ask_weathergpt",
                               side_effect=RuntimeError("boom")):
            r = self.client.post("/api/chat", json={"message": "hi"})
        self.assertEqual(r.status_code, 503)

    def test_alerts_not_configured_is_not_reported_as_no_alerts(self):
        r = self.client.get("/api/alerts", params={"location": "Bhopal"})
        body = r.json()
        self.assertEqual(body["status"], "not_configured")
        self.assertEqual(body["alerts"], [])
        self.assertEqual(
            body["message"],
            "Weather alert data is not configured for this location.")

    def test_climate_requires_dates_and_validates(self):
        base = {"lat": 23.2599, "lon": 77.4126}
        self.assertIn("start_date", self.client.get(
            "/api/climate", params=base).json()["message"])
        r = self.client.get("/api/climate", params={
            **base, "start_date": "2025-09-05", "end_date": "2025-09-01"})
        self.assertEqual(r.status_code, 422)
        ok = self.client.get("/api/climate", params={
            **base, "start_date": "2025-09-01", "end_date": "2025-09-01"})
        self.assertEqual(ok.json()["history"][0]["temperature_max"], 31.0)


if __name__ == "__main__":
    unittest.main()
