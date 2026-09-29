"""Unit tests for the hallucination guard and its interaction with the
rule-based advisory (which must never be blocked by the guard)."""

import os
import unittest
from unittest import mock

from tests.fixtures import FakeRequests

from ai.agents import weather_agent as wa
from ai.agents.advisory_agent import generate_advisory
from ai.guardrails.hallucination_check import (
    check_current_weather_response,
    check_forecast_response,
)

CURRENT = {"temperature": 24.1, "humidity": 80, "feels_like": 27.1,
           "precipitation": 0.0, "rain": 0.0, "wind_speed": 7.5,
           "wind_direction": 180, "cloud_cover": 40}


class TestCurrentWeatherGuard(unittest.TestCase):
    def test_faithful_response_passes(self):
        text = ("Currently 24.1°C, feels like 27.1°C, humidity 80%, "
                "wind 7.5 km/h.")
        self.assertTrue(check_current_weather_response(text, CURRENT)["safe"])

    def test_one_correct_number_does_not_excuse_fabricated_ones(self):
        text = "It is 24.1°C but there is 95% humidity and 60 km/h wind."
        self.assertFalse(check_current_weather_response(text, CURRENT)["safe"])

    def test_fabricated_only(self):
        self.assertFalse(check_current_weather_response(
            "It is 41°C.", CURRENT)["safe"])

    def test_rounded_whole_numbers_are_accepted(self):
        self.assertTrue(check_current_weather_response(
            "About 24°C with 80% humidity.", CURRENT)["safe"])

    def test_no_numbers_and_empty_and_error_are_unsafe(self):
        self.assertFalse(check_current_weather_response("Nice day.", CURRENT)["safe"])
        self.assertFalse(check_current_weather_response("", CURRENT)["safe"])
        self.assertFalse(check_current_weather_response(
            "24.1", {"error": "x"})["safe"])
        self.assertFalse(check_current_weather_response("24.1", None)["safe"])


class TestForecastGuard(unittest.TestCase):
    DATA = {"forecast": [{"date": "2026-09-29", "temperature_max": 34.0,
                          "temperature_min": 24.0,
                          "precipitation_probability": 80,
                          "precipitation": 2.4, "wind_speed_max": 15.0}],
            "period_forecast": {"status": "available", "temperature_min": 30.8,
                                "temperature_max": 32.0,
                                "precipitation_probability_max": 80,
                                "precipitation_sum": 0.8, "wind_speed_max": 12.0,
                                "hours": [{"temperature": 30.8, "humidity": 70}]}}

    def test_dates_and_times_are_not_treated_as_weather_values(self):
        text = ("On 2026-09-29 between 17:00 and 20:00 (5 PM to 8 PM, next "
                "24 hours) expect 30.8°C to 32°C and an 80% chance of rain.")
        self.assertTrue(check_forecast_response(text, self.DATA)["safe"])

    def test_coincidental_match_does_not_pass(self):
        # 70 equals an hourly humidity value; 45 and 95 are invented.
        text = "It will be 45°C with a 95% chance of rain and 70 km/h winds."
        self.assertFalse(check_forecast_response(text, self.DATA)["safe"])

    def test_hyphen_range_is_not_negative(self):
        self.assertTrue(check_forecast_response(
            "Between 30.8-32°C with 80% rain chance.", self.DATA)["safe"])


class TestRuleBasedAdvisoryIsNeverBlocked(unittest.TestCase):
    """The deterministic fallback must satisfy the (stricter) guard."""

    def setUp(self):
        for p in (mock.patch("requests.get", FakeRequests()),
                  mock.patch.object(wa, "groq_client", None),
                  mock.patch.dict(os.environ, {"IMD_DISTRICT_IDS": ""})):
            p.start()
            self.addCleanup(p.stop)

    def test_forecast_periods(self):
        for period in ("full day", "morning", "afternoon", "evening", "night"):
            with self.subTest(period=period):
                wa.reset_conversation_context()
                result = wa.process_user_query(
                    f"Will it rain in Bhopal tomorrow {period}?")
                self.assertNotIn("error", result)
                text = generate_advisory(result)
                verdict = check_forecast_response(text, result["weather_data"])
                self.assertTrue(verdict["safe"], verdict)

    def test_current_weather(self):
        wa.reset_conversation_context()
        result = wa.process_user_query("What is the weather now in Delhi?")
        text = generate_advisory(result)
        verdict = check_current_weather_response(text, result["weather_data"])
        self.assertTrue(verdict["safe"], verdict)
        wa.reset_conversation_context()


if __name__ == "__main__":
    unittest.main()
