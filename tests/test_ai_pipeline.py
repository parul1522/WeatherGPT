"""Offline tests for the integrated WeatherGPT AI pipeline.

External services are replaced by ``tests.fixtures.FakeRequests`` (Open-Meteo
and IMD) and, where needed, a fake Groq client. Everything else - query
understanding, context merge, tools, validation, hallucination guard,
translation, the backend ``ai_service`` layer - is the real code.

Run from the project root:  python -m unittest discover -s tests -t . -v
(or ``pytest``)
"""

import json
import os
import re
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from tests.fixtures import FakeRequests

from ai.agents import weather_agent as wa
from backend.app.services import ai_service

TOMORROW = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
TODAY = datetime.now().strftime("%Y-%m-%d")


def chat(session, text):
    return ai_service.answer_chat(text, session)["reply"]


class PipelineTestCase(unittest.TestCase):
    """Fresh sessions, no LLM, mocked network."""

    network_down = False

    def setUp(self):
        ai_service.reset_sessions()
        self.fake = FakeRequests(fail=self.network_down)
        for patcher in (
            mock.patch("requests.get", self.fake),
            mock.patch.object(wa, "groq_client", None),
            mock.patch.dict(os.environ, {"IMD_DISTRICT_IDS": ""}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)


class TestWeatherAndForecast(PipelineTestCase):
    def test_current_weather(self):
        reply = chat("s", "What is the weather now in Delhi?")
        self.assertIn("Current weather in Delhi", reply)
        self.assertIn("36.0", reply)

    def test_tomorrow_forecast(self):
        reply = chat("s", "Will it rain tomorrow in Bhopal?")
        self.assertIn(f"Forecast for Bhopal on {TOMORROW}", reply)
        self.assertIn("80%", reply)

    def test_specific_periods(self):
        for period in ("morning", "afternoon", "evening", "night"):
            with self.subTest(period=period):
                reply = chat(
                    f"p-{period}",
                    f"What is the forecast for Bhopal tomorrow {period}?")
                self.assertIn(f"Time period: {period}", reply)
                self.assertIn(TOMORROW, reply)

    def test_precipitation_has_no_float_noise(self):
        reply = chat("s", "Will it rain tomorrow in Bhopal?")
        self.assertNotRegex(reply, r"\d\.\d{4,}")

    def test_parameter_change_wind(self):
        reply = chat("s", "Will it be windy tomorrow in Pune?")
        self.assertIn("Pune", reply)
        self.assertIn("31.0 km/h", reply)


class TestConversationContext(PipelineTestCase):
    def test_followup_inherits_location_and_date(self):
        chat("s", "Will it rain tomorrow in Bhopal?")
        reply = chat("s", "What about evening?")
        self.assertIn(f"Forecast for Bhopal on {TOMORROW}", reply)
        self.assertIn("Time period: evening", reply)

    def test_location_change_keeps_date_and_time(self):
        chat("s", "Will it rain tomorrow in Bhopal?")
        chat("s", "What about evening?")
        reply = chat("s", "What about Mumbai tomorrow evening?")
        self.assertIn("Forecast for Mumbai", reply)
        self.assertIn("Time period: evening", reply)
        self.assertIn("15%", reply)  # Mumbai data, not Bhopal's 80%

    def test_location_override_alone_keeps_rest(self):
        chat("s", "Will it rain tomorrow in Bhopal?")
        chat("s", "What about evening?")
        reply = chat("s", "What about Mumbai?")
        self.assertIn("Forecast for Mumbai", reply)
        self.assertIn(TOMORROW, reply)
        self.assertIn("Time period: evening", reply)

    def test_there_refers_to_previous_location(self):
        chat("s", "What about Mumbai tomorrow evening?")
        reply = chat("s", "Will it rain there tomorrow morning?")
        self.assertIn("Forecast for Mumbai", reply)
        self.assertIn("Time period: morning", reply)

    def test_sessions_are_isolated(self):
        chat("alice", "Will it rain tomorrow in Bhopal?")
        reply = chat("bob", "What about evening?")
        self.assertIn("Location not detected", reply)
        self.assertNotIn("Bhopal", reply)

    def test_session_id_is_generated_and_reusable(self):
        first = ai_service.answer_chat("Will it rain tomorrow in Bhopal?")
        self.assertTrue(first["session_id"])
        second = ai_service.answer_chat("What about evening?", first["session_id"])
        self.assertIn("Forecast for Bhopal", second["reply"])

    def test_legacy_global_context_still_works(self):
        wa.reset_conversation_context()
        wa.ask_weathergpt("Will it rain tomorrow in Bhopal?")
        reply = wa.ask_weathergpt("What about evening?")
        self.assertIn("Forecast for Bhopal", reply)
        wa.reset_conversation_context()


class TestHindi(PipelineTestCase):
    def test_hindi_query_gets_hindi_reply(self):
        result = ai_service.answer_chat("कल भोपाल में बारिश होगी क्या?", "s")
        self.assertEqual(result["lang"], "hi")
        self.assertRegex(result["reply"], r"[\u0900-\u097F]")
        self.assertIn("80%", result["reply"])
        self.assertNotIn("Time period:", result["reply"])
        self.assertNotIn("Maximum wind speed", result["reply"])
        self.assertRegex(result["reply"], r"समय अवधि: (पूरा दिन|सुबह|दोपहर|शाम|रात)")

    def test_english_after_hindi_is_english(self):
        chat("s", "कल भोपाल में बारिश होगी क्या?")
        result = ai_service.answer_chat("What about Mumbai tomorrow evening?", "s")
        self.assertEqual(result["lang"], "en")
        self.assertIn("Forecast for Mumbai", result["reply"])

    def test_hindi_error_is_hindi(self):
        reply = chat("s", "कल बारिश होगी क्या?")
        self.assertRegex(reply, r"[\u0900-\u097F]")


class TestLocationHandling(PipelineTestCase):
    def test_invalid_location(self):
        reply = chat("s", "What is the weather in Atlantis?")
        self.assertIn("Atlantis", reply)
        self.assertIn("not configured", reply)

    def test_invalid_location_does_not_fall_back_to_previous_city(self):
        chat("s", "Will it rain tomorrow in Bhopal?")
        reply = chat("s", "What is the weather in Atlantis?")
        self.assertIn("not configured", reply)
        self.assertNotIn("Bhopal", reply)

    def test_missing_location(self):
        reply = chat("s", "Will it rain tomorrow?")
        self.assertIn("Location not detected", reply)


class TestAlerts(PipelineTestCase):
    def test_not_configured(self):
        reply = chat("s", "Are there any weather alerts for Bhopal?")
        self.assertEqual(
            reply, "Weather alert data is not configured for this location.")
        self.assertNotIn("No active", reply)
        self.assertEqual(self.fake.calls, [])  # IMD was never queried

    def test_actual_alert_data(self):
        self.fake.imd_payload = {
            "Date": "2026-09-29", "District": "BHOPAL",
            "Day_1": "2,4", "Day1_Color": 2,
            "Day_2": "1", "Day2_Color": 4}
        with mock.patch.dict(os.environ, {"IMD_DISTRICT_IDS": '{"Bhopal": 573}'}):
            reply = chat("s", "Are there any weather alerts for Bhopal?")
        self.assertIn("Heavy Rain", reply)
        self.assertIn("Orange alert", reply)
        self.assertNotIn("Day 2", reply)
        self.assertEqual(self.fake.calls[0][1], {"id": 573})

    def test_confirmed_no_active_alerts(self):
        self.fake.imd_payload = {
            "Date": "2026-09-29", "District": "BHOPAL",
            "Day_1": "1", "Day1_Color": 4}
        with mock.patch.dict(os.environ, {"IMD_DISTRICT_IDS": '{"Bhopal": 573}'}):
            reply = chat("s", "Are there any weather alerts for Bhopal?")
        self.assertIn("No active weather warnings for Bhopal", reply)

    def test_provider_unavailable_is_not_reported_as_no_alerts(self):
        self.fake.imd_fail = True
        with mock.patch.dict(os.environ, {"IMD_DISTRICT_IDS": '{"Bhopal": 573}'}):
            reply = chat("s", "Are there any weather alerts for Bhopal?")
        self.assertIn("currently unavailable", reply)
        self.assertNotIn("No active", reply)

    def test_alert_in_hindi(self):
        reply = chat("s", "भोपाल में मौसम चेतावनी है क्या?")
        self.assertRegex(reply, r"[\u0900-\u097F]")
        self.assertNotIn("No active", reply)

    def test_malformed_district_config_is_ignored(self):
        for bad in ("not json", "[1,2]", '{"Bhopal": "abc"}'):
            with mock.patch.dict(os.environ, {"IMD_DISTRICT_IDS": bad}):
                reply = chat("s", "Are there any weather alerts for Bhopal?")
            self.assertIn("not configured", reply)


class TestApiFailure(PipelineTestCase):
    network_down = True

    def test_current_weather_api_down(self):
        reply = chat("s", "What is the weather now in Delhi?")
        self.assertIn("Unable to retrieve weather data", reply)
        self.assertNotRegex(reply, r"\d+(\.\d+)?\s?°C")

    def test_forecast_api_down(self):
        reply = chat("s", "Will it rain tomorrow in Bhopal?")
        self.assertIn("Unable to retrieve forecast data", reply)
        self.assertNotIn("%", reply)


class TestInvalidData(PipelineTestCase):
    def test_missing_current_fields(self):
        bad = {"temperature": None, "humidity": 50, "precipitation": 0,
               "wind_speed": 3}
        with mock.patch.object(wa, "get_current_weather", return_value=bad):
            reply = chat("s", "What is the weather now in Delhi?")
        self.assertIn("Missing weather data: temperature", reply)

    def test_out_of_range_humidity(self):
        bad = {"temperature": 20, "humidity": 150, "precipitation": 0,
               "wind_speed": 3}
        with mock.patch.object(wa, "get_current_weather", return_value=bad):
            reply = chat("s", "What is the weather now in Delhi?")
        self.assertIn("Invalid humidity", reply)

    def test_missing_period_data(self):
        real_get_forecast = wa.get_forecast

        def no_hours(*args, **kwargs):
            data = real_get_forecast(*args, **kwargs)
            data["period_forecast"] = {"status": "unavailable"}
            return data

        with mock.patch.object(wa, "get_forecast", side_effect=no_hours):
            reply = chat("s", "What is the forecast for Bhopal tomorrow evening?")
        self.assertIn("not available for the requested time period", reply)


class FakeGroq:
    """Stands in for the Groq client. ``answer`` is the LLM's reply text."""

    def __init__(self, answer, understanding=None):
        self.answer, self.understanding, self.calls = answer, understanding, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if "response_format" in kwargs:  # query-understanding call
            if self.understanding is None:
                raise RuntimeError("no understanding configured")
            content = json.dumps(self.understanding)
        else:
            content = self.answer
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=content))])


class TestHallucinationGuard(PipelineTestCase):
    def test_fabricated_numbers_are_blocked(self):
        llm = FakeGroq("Tomorrow in Bhopal it will be 45°C with a 95% chance "
                       "of rain and 70 km/h winds.")
        with mock.patch.object(wa, "groq_client", llm):
            reply = chat("s", "Will it rain tomorrow in Bhopal?")
        self.assertTrue(llm.calls, "LLM path was not exercised")
        self.assertNotIn("45", reply)
        self.assertNotIn("95%", reply)
        self.assertIn("80%", reply)  # rule-based answer from verified data

    def test_faithful_llm_answer_is_used_and_query_understanding_via_llm(self):
        llm = FakeGroq(
            "Tomorrow evening in Bhopal there is an 80% chance of rain.",
            understanding={"intent": "forecast", "location": "Bhopal",
                           "date": "tomorrow", "time_range": "evening",
                           "weather_parameter": "rain", "language": "en"})
        with mock.patch.object(wa, "groq_client", llm):
            reply = chat("s", "Will it rain tomorrow evening in Bhopal?")
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("80% chance of rain", reply)

    def test_llm_failure_falls_back_to_verified_rule_based_answer(self):
        class Boom(FakeGroq):
            def _create(self, **kwargs):
                raise RuntimeError("groq down")
        llm = Boom("x")
        with mock.patch.object(wa, "groq_client", llm):
            reply = chat("s", "Will it rain tomorrow in Bhopal?")
        self.assertIn("Forecast for Bhopal", reply)
        self.assertIn("80%", reply)


class TestServiceLayer(PipelineTestCase):
    def test_unexpected_failure_becomes_ai_service_error(self):
        with mock.patch.object(ai_service, "ask_weathergpt",
                               side_effect=RuntimeError("boom")):
            with self.assertRaises(ai_service.AIServiceError):
                ai_service.answer_chat("hello", "s")

    def test_climate_tool_available_through_service(self):
        from backend.app.services.climate_service import get_climate
        data = get_climate(23.2599, 77.4126, "2025-09-01", "2025-09-01")
        self.assertEqual(data["history"][0]["temperature_max"], 31.0)
        with self.assertRaises(ValueError):
            get_climate(23.2599, 77.4126, "2025-09-05", "2025-09-01")
        with self.assertRaises(ValueError):
            get_climate(23.2599, 77.4126, "garbage", "2025-09-01")


if __name__ == "__main__":
    unittest.main()
