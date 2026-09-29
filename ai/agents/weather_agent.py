import os
import json
import re
from datetime import datetime, timedelta

try:
    from groq import Groq
except ImportError:  # groq SDK not installed -> run without the LLM
    Groq = None

from ai.config import get_groq_api_key, get_groq_model

from ai.tools.weather_tool import get_current_weather
from ai.tools.forecast_tool import get_forecast
from ai.tools.alert_tool import get_weather_alerts

from ai.language.detector import parse_user_query
from ai.language.translator import translate_response

from ai.agents.advisory_agent import generate_advisory
from ai.agents.alert_agent import format_alert_response

from ai.guardrails.validation import (
    validate_weather_data,
    validate_forecast_data
)

from ai.guardrails.hallucination_check import (
    check_current_weather_response,
    check_forecast_response
)


# --------------------------------------------------
# GROQ CONFIGURATION
# --------------------------------------------------

GROQ_MODEL = get_groq_model()

groq_client = None

_groq_api_key = get_groq_api_key()

if _groq_api_key and Groq is not None:
    groq_client = Groq(
        api_key=_groq_api_key
    )
elif _groq_api_key and Groq is None:
    print(
        "\n[Config warning] GROQ_API_KEY is set but the "
        "'groq' package is not installed. Running without the LLM."
    )


# --------------------------------------------------
# TEMPORARY LOCATION DATABASE
# --------------------------------------------------

LOCATIONS = {
    "Bhopal": {
        "latitude": 23.2599,
        "longitude": 77.4126
    },
    "Delhi": {
        "latitude": 28.6139,
        "longitude": 77.2090
    },
    "Mumbai": {
        "latitude": 19.0760,
        "longitude": 72.8777
    },
    "Indore": {
        "latitude": 22.7196,
        "longitude": 75.8577
    },
    "Pune": {
        "latitude": 18.5204,
        "longitude": 73.8567
    },
    "Bengaluru": {
        "latitude": 12.9716,
        "longitude": 77.5946
    },
    "Kolkata": {
        "latitude": 22.5726,
        "longitude": 88.3639
    },
    "Chennai": {
        "latitude": 13.0827,
        "longitude": 80.2707
    },
    "Hyderabad": {
        "latitude": 17.3850,
        "longitude": 78.4867
    },
    "Jaipur": {
        "latitude": 26.9124,
        "longitude": 75.7873
    },
    "Lucknow": {
        "latitude": 26.8467,
        "longitude": 80.9462
    },
    "Ahmedabad": {
        "latitude": 23.0225,
        "longitude": 72.5714
    }
}


# --------------------------------------------------
# CONVERSATION CONTEXT
# --------------------------------------------------

CONVERSATION_CONTEXT = {
    "intent": None,
    "location": None,
    "date": None,
    "time_range": None,
    "weather_parameter": None,
    "language": "en"
}


def reset_conversation_context():
    """
    Reset the current conversation context.

    This can be used when starting a completely
    new conversation.
    """

    global CONVERSATION_CONTEXT

    CONVERSATION_CONTEXT = {
        "intent": None,
        "location": None,
        "date": None,
        "time_range": None,
        "weather_parameter": None,
        "language": "en"
    }


# --------------------------------------------------
# NORMALIZE QUERY ENTITIES
# --------------------------------------------------

def normalize_query_entities(
    question: str,
    parsed_query: dict
) -> dict:
    """
    Add deterministic entity extraction on top of
    the LLM result.

    The LLM remains the main semantic parser.

    This function acts as a safety layer for common
    date, time-range, and weather-parameter phrases.
    """

    if not question:
        return parsed_query

    text = question.lower().strip()

    result = parsed_query.copy()

    # --------------------------------------------------
    # DATE EXTRACTION
    # --------------------------------------------------

    if (
        re.search(r"\btomorrow\b", text)
        or "कल" in text
    ):
        result["date"] = "tomorrow"

    elif (
        re.search(r"\btoday\b", text)
        or "आज" in text
    ):
        result["date"] = "today"

    elif (
        re.search(r"\btonight\b", text)
        or "आज रात" in text
        or "रात" in text
    ):
        result["date"] = "today"

    # --------------------------------------------------
    # TIME RANGE EXTRACTION
    # --------------------------------------------------

    if (
        re.search(r"\bmorning\b", text)
        or "सुबह" in text
    ):
        result["time_range"] = "morning"

    elif (
        re.search(r"\bafternoon\b", text)
        or "दोपहर" in text
    ):
        result["time_range"] = "afternoon"

    elif (
        re.search(r"\bevening\b", text)
        or "शाम" in text
    ):
        result["time_range"] = "evening"

    elif (
        re.search(r"\bnight\b", text)
        or re.search(r"\btonight\b", text)
        or "रात" in text
    ):
        result["time_range"] = "night"

    # --------------------------------------------------
    # TONIGHT
    # --------------------------------------------------

    if (
        re.search(r"\btonight\b", text)
        or "आज रात" in text
    ):
        result["date"] = "today"
        result["time_range"] = "night"

    # --------------------------------------------------
    # WEATHER PARAMETER
    # --------------------------------------------------

    if (
        re.search(r"\brain\b", text)
        or re.search(r"\braining\b", text)
        or re.search(r"\bumbrella\b", text)
        or "बारिश" in text
        or "वर्षा" in text
        or "बरसात" in text
        or "छाता" in text
    ):
        result["weather_parameter"] = "rain"

    elif (
        re.search(r"\btemperature\b", text)
        or re.search(r"\bhot\b", text)
        or re.search(r"\bcold\b", text)
        or re.search(r"\bheat\b", text)
        or "तापमान" in text
        or "गर्मी" in text
        or "ठंड" in text
    ):
        result["weather_parameter"] = "temperature"

    elif (
        re.search(r"\bwind\b", text)
        or re.search(r"\bwindy\b", text)
        or "हवा" in text
    ):
        result["weather_parameter"] = "wind"

    elif (
        re.search(r"\bhumidity\b", text)
        or "आर्द्रता" in text
    ):
        result["weather_parameter"] = "humidity"

    # --------------------------------------------------
    # LOCATION EXTRACTION
    # --------------------------------------------------

    detected_location = None

    for city in LOCATIONS:

        city_lower = city.lower()

        if re.search(
            rf"\b{re.escape(city_lower)}\b",
            text
        ):
            detected_location = city
            break

    # Hindi / alternate city names
    location_aliases = {
        "भोपाल": "Bhopal",
        "दिल्ली": "Delhi",
        "मुंबई": "Mumbai",
        "इंदौर": "Indore",
        "पुणे": "Pune",
        "बेंगलुरु": "Bengaluru",
        "बैंगलोर": "Bengaluru",
        "कोलकाता": "Kolkata",
        "चेन्नई": "Chennai",
        "हैदराबाद": "Hyderabad",
        "जयपुर": "Jaipur",
        "लखनऊ": "Lucknow",
        "अहमदाबाद": "Ahmedabad"
    }

    for alias, city in location_aliases.items():

        if alias in text:

            detected_location = city
            break

    if detected_location:
        result["location"] = detected_location

    # --------------------------------------------------
    # COMMON FOLLOW-UP LOCATION WORD
    # --------------------------------------------------

    # Words such as "there" intentionally do not
    # create a new location.
    #
    # The conversation context will preserve the
    # previous location.

    if re.search(
        r"\bthere\b",
        text
    ):
        if not detected_location:
            result["location"] = None

    if "वहां" in text or "वहाँ" in text:

        if not detected_location:
            result["location"] = None

    # --------------------------------------------------
    # COMMON FORECAST INTENT
    # --------------------------------------------------

    forecast_phrases = [
        "will it rain",
        "will it be",
        "forecast",
        "tomorrow",
        "tonight",
        "this evening",
        "this morning",
        "this afternoon",
        "what about",
        "rain tomorrow",
        "बारिश होगी",
        "बारिश होने",
        "पूर्वानुमान"
    ]

    if any(
        phrase in text
        for phrase in forecast_phrases
    ):

        if result.get("intent") == "unknown":
            result["intent"] = "forecast"

    # --------------------------------------------------
    # CURRENT WEATHER INTENT
    # --------------------------------------------------

    current_phrases = [
        "right now",
        "currently",
        "current weather",
        "current temperature",
        "weather now",
        "अभी",
        "वर्तमान मौसम"
    ]

    if any(
        phrase in text
        for phrase in current_phrases
    ):

        result["intent"] = "current_weather"

    # --------------------------------------------------
    # ALERT INTENT
    # --------------------------------------------------

    alert_phrases = [
        "alert",
        "warning",
        "cyclone",
        "flood warning",
        "storm warning",
        "चेतावनी",
        "बाढ़ चेतावनी",
        "तूफान"
    ]

    if any(
        phrase in text
        for phrase in alert_phrases
    ):

        result["intent"] = "alert"

    # --------------------------------------------------
    # CLIMATE INTENT
    # --------------------------------------------------

    climate_phrases = [
        "historical",
        "history",
        "climate",
        "trend",
        "past weather",
        "इतिहास",
        "जलवायु",
        "रुझान"
    ]

    if any(
        phrase in text
        for phrase in climate_phrases
    ):

        result["intent"] = "climate"

    return result


# --------------------------------------------------
# MERGE CONVERSATION CONTEXT
# --------------------------------------------------

def merge_conversation_context(
    current_query: dict,
    context: dict = None
) -> dict:
    """
    Merge the current user query with the previous
    conversation context.

    Explicit information from the current query
    always takes priority.

    Missing or unknown information can be inherited
    from the previous query.

    Args:
        current_query:
            Parsed query for the current message.

        context:
            Optional per-session context dictionary. It is
            read for inherited values and updated in place.
            When omitted, the module-level default context
            (single-user / CLI mode) is used, exactly as before.
    """

    global CONVERSATION_CONTEXT

    if context is None:
        previous_context = CONVERSATION_CONTEXT
    else:
        previous_context = context

    merged = {}

    # --------------------------------------------------
    # INTENT
    # --------------------------------------------------

    current_intent = current_query.get(
        "intent"
    )

    if (
        current_intent
        and current_intent != "unknown"
    ):

        merged["intent"] = current_intent

    else:

        merged["intent"] = (
            previous_context.get(
                "intent"
            )
            or "unknown"
        )

    # --------------------------------------------------
    # LOCATION
    # --------------------------------------------------

    current_location = current_query.get(
        "location"
    )

    if current_location:

        merged["location"] = current_location

    else:

        merged["location"] = (
            previous_context.get(
                "location"
            )
        )

    # --------------------------------------------------
    # DATE
    # --------------------------------------------------

    current_date = current_query.get(
        "date"
    )

    if current_date:

        merged["date"] = current_date

    else:

        merged["date"] = (
            previous_context.get(
                "date"
            )
        )

    # --------------------------------------------------
    # TIME RANGE
    # --------------------------------------------------

    current_time_range = current_query.get(
        "time_range"
    )

    if (
        current_time_range
        and current_time_range != "unknown"
    ):

        merged["time_range"] = current_time_range

    else:

        merged["time_range"] = (
            previous_context.get(
                "time_range"
            )
            or "unknown"
        )

    # --------------------------------------------------
    # WEATHER PARAMETER
    # --------------------------------------------------

    current_parameter = current_query.get(
        "weather_parameter"
    )

    if (
        current_parameter
        and current_parameter != "general"
    ):

        merged["weather_parameter"] = (
            current_parameter
        )

    else:

        previous_parameter = (
            previous_context.get(
                "weather_parameter"
            )
        )

        merged["weather_parameter"] = (
            previous_parameter
            or "general"
        )

    # --------------------------------------------------
    # LANGUAGE
    # --------------------------------------------------

    current_language = current_query.get(
        "language"
    )

    if current_language:

        merged["language"] = current_language

    else:

        merged["language"] = (
            previous_context.get(
                "language"
            )
            or "en"
        )

    # --------------------------------------------------
    # UPDATE GLOBAL CONTEXT
    # --------------------------------------------------

    if context is None:

        CONVERSATION_CONTEXT = merged.copy()

    else:

        context.clear()
        context.update(merged)

    return merged


# --------------------------------------------------
# LOAD SYSTEM PROMPT
# --------------------------------------------------

def load_prompt(filename: str) -> str:
    """
    Load a prompt from the prompts folder.
    """

    prompt_path = os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        ),
        "prompts",
        filename
    )

    try:

        with open(
            prompt_path,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    except FileNotFoundError:

        return ""


# --------------------------------------------------
# RESOLVE REQUESTED DATE
# --------------------------------------------------

def resolve_requested_date(
    requested_date: str
) -> str | None:
    """
    Convert natural date expressions into YYYY-MM-DD.

    Supported:
        today
        tomorrow
        YYYY-MM-DD

    Returns:
        A date string in YYYY-MM-DD format,
        or None if the date cannot be resolved.
    """

    if not requested_date:
        return None

    requested_date = str(
        requested_date
    ).strip().lower()

    today = datetime.now().date()

    if requested_date == "today":

        return today.strftime(
            "%Y-%m-%d"
        )

    if requested_date == "tomorrow":

        tomorrow = today + timedelta(
            days=1
        )

        return tomorrow.strftime(
            "%Y-%m-%d"
        )

    # Already an ISO date
    try:

        parsed_date = datetime.strptime(
            requested_date,
            "%Y-%m-%d"
        )

        return parsed_date.strftime(
            "%Y-%m-%d"
        )

    except ValueError:

        return None


# --------------------------------------------------
# LLM QUERY UNDERSTANDING
# --------------------------------------------------

def understand_user_query(
    question: str
) -> dict:
    """
    Use Groq to understand the user's natural-language
    weather question.

    Returns structured information about:
        - intent
        - location
        - date
        - time range
        - weather parameter
        - language

    Falls back to the existing rule-based detector
    if Groq is unavailable or fails.
    """

    # --------------------------------------------------
    # RULE-BASED FALLBACK
    # --------------------------------------------------

    fallback = parse_user_query(
        question
    )

    default_result = {
        "intent": fallback.get(
            "intent",
            "unknown"
        ),
        "location": fallback.get(
            "location"
        ),
        "date": None,
        "time_range": "unknown",
        "weather_parameter": "general",
        "language": fallback.get(
            "language",
            "en"
        )
    }

    if groq_client is None:

        return normalize_query_entities(
            question,
            default_result
        )

    # --------------------------------------------------
    # QUERY UNDERSTANDING PROMPT
    # --------------------------------------------------

    system_prompt = """
You are the query-understanding component of WeatherGPT.

Convert the user's weather question into structured data.

You MUST return a JSON object containing exactly these
six fields:

intent
location
date
time_range
weather_parameter
language

Allowed intent values:

current_weather
forecast
alert
climate
unknown

Allowed time_range values:

morning
afternoon
evening
night
full_day
unknown

Allowed weather_parameter values:

temperature
rain
wind
humidity
general

Rules:

1. Detect the user's main weather intent.

2. Extract the city if explicitly mentioned.

3. If no city is mentioned, location must be null.

4. Understand:
   today
   tomorrow
   tonight
   morning
   afternoon
   evening
   night
   weekend

5. "Tonight" means:
   date = today
   time_range = night

6. Preserve the user's language.

7. Do not invent a location.

8. Do not invent a date.

9. If information is unclear, use null or "unknown".

10. "Will it rain" means weather_parameter = "rain".

11. "Umbrella" usually indicates rain or precipitation.

12. "Temperature", "hot", or "cold" means
    weather_parameter = "temperature".

13. "Wind" or "windy" means
    weather_parameter = "wind".

14. "Humidity" means
    weather_parameter = "humidity".

15. General weather questions use weather_parameter =
    "general".

16. Short follow-up questions may intentionally omit
    location, date, intent, or weather parameter.

17. In follow-up questions, do NOT invent missing
    information. Return null or "unknown".

18. If the user says "there", "वहां", or "वहाँ",
    location must be null unless a new city is explicitly
    mentioned.

Examples:

Question:
What's the weather in Bhopal?

JSON:
{
  "intent": "current_weather",
  "location": "Bhopal",
  "date": "today",
  "time_range": "full_day",
  "weather_parameter": "general",
  "language": "en"
}

Question:
Will it rain tomorrow in Delhi?

JSON:
{
  "intent": "forecast",
  "location": "Delhi",
  "date": "tomorrow",
  "time_range": "full_day",
  "weather_parameter": "rain",
  "language": "en"
}

Question:
Do I need an umbrella in Mumbai tomorrow evening?

JSON:
{
  "intent": "forecast",
  "location": "Mumbai",
  "date": "tomorrow",
  "time_range": "evening",
  "weather_parameter": "rain",
  "language": "en"
}

Question:
What about evening?

JSON:
{
  "intent": "unknown",
  "location": null,
  "date": null,
  "time_range": "evening",
  "weather_parameter": "general",
  "language": "en"
}

Question:
Will it rain there tomorrow?

JSON:
{
  "intent": "forecast",
  "location": null,
  "date": "tomorrow",
  "time_range": "full_day",
  "weather_parameter": "rain",
  "language": "en"
}

Question:
What about tomorrow morning?

JSON:
{
  "intent": "unknown",
  "location": null,
  "date": "tomorrow",
  "time_range": "morning",
  "weather_parameter": "general",
  "language": "en"
}

Question:
What about tonight?

JSON:
{
  "intent": "unknown",
  "location": null,
  "date": "today",
  "time_range": "night",
  "weather_parameter": "general",
  "language": "en"
}

Question:
कल भोपाल में बारिश होगी क्या?

JSON:
{
  "intent": "forecast",
  "location": "Bhopal",
  "date": "tomorrow",
  "time_range": "full_day",
  "weather_parameter": "rain",
  "language": "hi"
}
"""

    user_prompt = f"""
Convert this user question into the required JSON structure:

{question}
"""

    # --------------------------------------------------
    # JSON SCHEMA
    # --------------------------------------------------

    response_schema = {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "current_weather",
                    "forecast",
                    "alert",
                    "climate",
                    "unknown"
                ]
            },
            "location": {
                "type": [
                    "string",
                    "null"
                ]
            },
            "date": {
                "type": [
                    "string",
                    "null"
                ]
            },
            "time_range": {
                "type": "string",
                "enum": [
                    "morning",
                    "afternoon",
                    "evening",
                    "night",
                    "full_day",
                    "unknown"
                ]
            },
            "weather_parameter": {
                "type": "string",
                "enum": [
                    "temperature",
                    "rain",
                    "wind",
                    "humidity",
                    "general"
                ]
            },
            "language": {
                "type": "string",
                "enum": [
                    "en",
                    "hi"
                ]
            }
        },
        "required": [
            "intent",
            "location",
            "date",
            "time_range",
            "weather_parameter",
            "language"
        ],
        "additionalProperties": False
    }

    # --------------------------------------------------
    # CALL GROQ
    # --------------------------------------------------

    try:

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=0,
            max_completion_tokens=300,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "weather_query",
                    "strict": True,
                    "schema": response_schema
                }
            }
        )

        content = response.choices[0].message.content

        if not content:

            return normalize_query_entities(
                question,
                default_result
            )

        content = content.strip()

        parsed = json.loads(
            content
        )

        # --------------------------------------------------
        # VALIDATE INTENT
        # --------------------------------------------------

        allowed_intents = {
            "current_weather",
            "forecast",
            "alert",
            "climate",
            "unknown"
        }

        intent = parsed.get(
            "intent"
        )

        if intent not in allowed_intents:

            intent = "unknown"

        # --------------------------------------------------
        # VALIDATE TIME RANGE
        # --------------------------------------------------

        allowed_time_ranges = {
            "morning",
            "afternoon",
            "evening",
            "night",
            "full_day",
            "unknown"
        }

        time_range = parsed.get(
            "time_range",
            "unknown"
        )

        if time_range not in allowed_time_ranges:

            time_range = "unknown"

        # --------------------------------------------------
        # VALIDATE WEATHER PARAMETER
        # --------------------------------------------------

        allowed_parameters = {
            "temperature",
            "rain",
            "wind",
            "humidity",
            "general"
        }

        weather_parameter = parsed.get(
            "weather_parameter",
            "general"
        )

        if weather_parameter not in allowed_parameters:

            weather_parameter = "general"

        # --------------------------------------------------
        # NORMALIZE LOCATION
        # --------------------------------------------------

        location = parsed.get(
            "location"
        )

        if location is not None:

            location = str(
                location
            ).strip()

            matched_location = None

            for city in LOCATIONS:

                if location.lower() == city.lower():

                    matched_location = city

                    break

            if matched_location:

                location = matched_location

            else:

                location = None

        # --------------------------------------------------
        # VALIDATE LANGUAGE
        # --------------------------------------------------

        language = parsed.get(
            "language",
            fallback.get(
                "language",
                "en"
            )
        )

        if language not in {
            "en",
            "hi"
        }:

            language = fallback.get(
                "language",
                "en"
            )

        # --------------------------------------------------
        # BUILD STRUCTURED QUERY
        # --------------------------------------------------

        structured_query = {
            "intent": intent,
            "location": location,
            "date": parsed.get(
                "date"
            ),
            "time_range": time_range,
            "weather_parameter": weather_parameter,
            "language": language
        }

        # --------------------------------------------------
        # DETERMINISTIC SAFETY LAYER
        # --------------------------------------------------

        structured_query = normalize_query_entities(
            question,
            structured_query
        )

        return structured_query

    except Exception as error:

        print(
            "\n[Query understanding warning]"
            f" {error}"
        )

        return normalize_query_entities(
            question,
            default_result
        )


# --------------------------------------------------
# LLM RESPONSE GENERATION
# --------------------------------------------------

def generate_llm_response(
    question: str,
    result: dict
) -> str:
    """
    Generate a natural-language response using Groq.

    The LLM receives only verified weather data.
    It must not invent weather information.
    """

    if groq_client is None:
        return ""

    weather_data = result.get(
        "weather_data"
    )

    intent = result.get(
        "intent"
    )

    location = result.get(
        "location"
    )

    if not weather_data:
        return ""

    system_prompt = load_prompt(
        "system_prompt.txt"
    )

    advisory_prompt = load_prompt(
        "advisory_prompt.txt"
    )

    parsed_query = result.get(
        "parsed_query",
        {}
    )

    # --------------------------------------------------
    # CREATE COMPACT DATA FOR THE LLM
    # --------------------------------------------------

    if intent == "current_weather":

        verified_data_for_llm = {
            "latitude": weather_data.get(
                "latitude"
            ),
            "longitude": weather_data.get(
                "longitude"
            ),
            "temperature": weather_data.get(
                "temperature"
            ),
            "humidity": weather_data.get(
                "humidity"
            ),
            "feels_like": weather_data.get(
                "feels_like"
            ),
            "precipitation": weather_data.get(
                "precipitation"
            ),
            "rain": weather_data.get(
                "rain"
            ),
            "weather_code": weather_data.get(
                "weather_code"
            ),
            "cloud_cover": weather_data.get(
                "cloud_cover"
            ),
            "wind_speed": weather_data.get(
                "wind_speed"
            ),
            "wind_direction": weather_data.get(
                "wind_direction"
            ),
            "timestamp": weather_data.get(
                "timestamp"
            ),
            "source": weather_data.get(
                "source"
            )
        }

    elif intent == "forecast":

        forecast = weather_data.get(
            "forecast",
            []
        )

        period_forecast = weather_data.get(
            "period_forecast"
        )

        # --------------------------------------------------
        # SPECIFIC TIME PERIOD
        # --------------------------------------------------

        if (
            period_forecast
            and period_forecast.get(
                "status"
            ) == "available"
        ):

            verified_data_for_llm = {
                "latitude": weather_data.get(
                    "latitude"
                ),
                "longitude": weather_data.get(
                    "longitude"
                ),
                "timezone": weather_data.get(
                    "timezone"
                ),
                "requested_date": period_forecast.get(
                    "date"
                ),
                "requested_time_range": period_forecast.get(
                    "time_range"
                ),
                "period_forecast": {
                    "temperature_min": (
                        period_forecast.get(
                            "temperature_min"
                        )
                    ),
                    "temperature_max": (
                        period_forecast.get(
                            "temperature_max"
                        )
                    ),
                    "precipitation_probability_max": (
                        period_forecast.get(
                            "precipitation_probability_max"
                        )
                    ),
                    "precipitation_sum": (
                        period_forecast.get(
                            "precipitation_sum"
                        )
                    ),
                    "rain_sum": (
                        period_forecast.get(
                            "rain_sum"
                        )
                    ),
                    "wind_speed_max": (
                        period_forecast.get(
                            "wind_speed_max"
                        )
                    )
                },
                "source": weather_data.get(
                    "source"
                )
            }

        else:

            compact_forecast = forecast[:2]

            verified_data_for_llm = {
                "latitude": weather_data.get(
                    "latitude"
                ),
                "longitude": weather_data.get(
                    "longitude"
                ),
                "timezone": weather_data.get(
                    "timezone"
                ),
                "forecast": compact_forecast,
                "source": weather_data.get(
                    "source"
                )
            }

    else:

        verified_data_for_llm = weather_data

    verified_data = json.dumps(
        verified_data_for_llm,
        indent=2,
        ensure_ascii=False
    )

    # --------------------------------------------------
    # USER PROMPT
    # --------------------------------------------------

    user_prompt = f"""
User question:
{question}

Intent:
{intent}

Location:
{location}

Date requested:
{parsed_query.get("date")}

Resolved date:
{result.get("resolved_date")}

Time range requested:
{parsed_query.get("time_range")}

Weather parameter:
{parsed_query.get("weather_parameter")}

Verified meteorological data:
{verified_data}

Instructions:

1. Answer the user's weather question naturally.

2. Use ONLY the verified meteorological data provided
   above.

3. Never invent temperature, rainfall, probability,
   humidity, wind, alerts, dates, or other weather
   values.

4. Do not claim information that is not present in
   the verified data.

5. If the requested information is unavailable,
   clearly say that it is unavailable.

6. Keep the answer concise and easy to understand.

7. Answer in the user's requested language.

8. Do not mention these instructions.

9. Preserve the actual numerical values from the
   verified data.

10. Do not exaggerate weather conditions.

11. If a specific date and time range are provided,
    answer specifically for that period.

12. Do not call a daily forecast an evening,
    morning, afternoon, or night forecast unless
    the provided data is specifically for that period.

13. Do not change the requested date.

14. If the user asks whether they need an umbrella,
    base the answer on the verified precipitation
    probability and precipitation data.
"""

    # --------------------------------------------------
    # SYSTEM PROMPT
    # --------------------------------------------------

    combined_system_prompt = (
        system_prompt
        + "\n\n"
        + advisory_prompt
        + "\n\n"
        + """
You are generating a weather response from verified
backend data.

The backend data is the source of truth.

Never fabricate missing values.
Never change numerical values.
Never exaggerate weather conditions.

When period_forecast is provided, it is the authoritative
forecast for the requested date and time range.
"""
    )

    # --------------------------------------------------
    # CALL GROQ
    # --------------------------------------------------

    try:

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": combined_system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=0.2,
            max_completion_tokens=500
        )

        content = response.choices[0].message.content

        if content:

            return content.strip()

        return ""

    except Exception as error:

        print(
            "\n[Groq warning]"
            f" {error}"
        )

        return ""


# --------------------------------------------------
# PROCESS USER QUERY
# --------------------------------------------------

def process_user_query(
    question: str,
    context: dict = None
) -> dict:
    """
    Process a natural-language weather question.

    Flow:

    User question
        ↓
    Groq query understanding
        ↓
    Entity normalization
        ↓
    Conversation context
        ↓
    Intent + location + date + time + parameter
        ↓
    Weather tool
        ↓
    Data validation
        ↓
    Structured result
    """

    parsed_query = understand_user_query(
        question
    )

    # --------------------------------------------------
    # MERGE WITH PREVIOUS CONVERSATION
    # --------------------------------------------------

    parsed_query = merge_conversation_context(
        parsed_query,
        context
    )

    intent = parsed_query[
        "intent"
    ]

    location = parsed_query[
        "location"
    ]

    # --------------------------------------------------
    # NORMALIZE LOCATION AGAINST DATABASE
    # --------------------------------------------------

    if location:

        for city in LOCATIONS:

            if location.lower() == city.lower():

                location = city

                parsed_query[
                    "location"
                ] = city

                break

    # --------------------------------------------------
    # LOCATION REQUIRED
    # --------------------------------------------------

    if location is None:

        return {
            "question": question,
            "parsed_query": parsed_query,
            "error": (
                "Location not detected. "
                "Please specify a city."
            )
        }

    # --------------------------------------------------
    # CHECK LOCATION
    # --------------------------------------------------

    if location not in LOCATIONS:

        return {
            "question": question,
            "parsed_query": parsed_query,
            "location": location,
            "error": (
                f"Weather data for {location} "
                "is not configured yet."
            )
        }

    coordinates = LOCATIONS[
        location
    ]

    latitude = coordinates[
        "latitude"
    ]

    longitude = coordinates[
        "longitude"
    ]

    # --------------------------------------------------
    # CURRENT WEATHER
    # --------------------------------------------------

    if intent == "current_weather":

        weather_data = get_current_weather(
            latitude,
            longitude
        )

        validation = validate_weather_data(
            weather_data
        )

        if not validation["valid"]:

            return {
                "question": question,
                "parsed_query": parsed_query,
                "location": location,
                "error": (
                    "Weather data validation failed: "
                    + validation["reason"]
                )
            }

    # --------------------------------------------------
    # FORECAST
    # --------------------------------------------------

    elif intent == "forecast":

        requested_date = parsed_query.get(
            "date"
        )

        time_range = parsed_query.get(
            "time_range",
            "full_day"
        )

        # --------------------------------------------------
        # NORMALIZE UNKNOWN TIME RANGE
        # --------------------------------------------------

        if time_range == "unknown":

            time_range = "full_day"

            parsed_query[
                "time_range"
            ] = time_range

        # --------------------------------------------------
        # RESOLVE TODAY / TOMORROW
        # --------------------------------------------------

        resolved_date = resolve_requested_date(
            requested_date
        )

        # --------------------------------------------------
        # IF DATE WAS NOT PROVIDED,
        # USE TODAY.
        # --------------------------------------------------

        if resolved_date is None:

            resolved_date = (
                datetime.now()
                .date()
                .strftime(
                    "%Y-%m-%d"
                )
            )

        # --------------------------------------------------
        # FETCH FORECAST
        # --------------------------------------------------

        weather_data = get_forecast(
            latitude,
            longitude,
            days=7,
            target_date=resolved_date,
            time_range=time_range
        )

        validation = validate_forecast_data(
            weather_data
        )

        if not validation["valid"]:

            return {
                "question": question,
                "parsed_query": parsed_query,
                "location": location,
                "error": (
                    "Forecast validation failed: "
                    + validation["reason"]
                )
            }

        # --------------------------------------------------
        # STORE RESOLVED DATE
        # --------------------------------------------------

        parsed_query[
            "resolved_date"
        ] = resolved_date

        # --------------------------------------------------
        # CHECK SPECIFIC PERIOD
        # --------------------------------------------------

        period_forecast = weather_data.get(
            "period_forecast"
        )

        if (
            time_range != "full_day"
            and (
                not period_forecast
                or period_forecast.get(
                    "status"
                ) != "available"
            )
        ):

            return {
                "question": question,
                "parsed_query": parsed_query,
                "location": location,
                "error": (
                    "Forecast data is not available "
                    "for the requested time period."
                )
            }

    # --------------------------------------------------
    # ALERT
    # --------------------------------------------------

    elif intent == "alert":

        # Official IMD data only. The tool reports one of:
        # available / not_configured / api_error /
        # invalid_response / empty_response / location_required.
        # Nothing is invented when the provider is unavailable.
        weather_data = get_weather_alerts(
            latitude,
            longitude,
            location
        )

        validation = {
            "valid": True,
            "reason": (
                "Alert status: "
                + str(weather_data.get("status"))
            )
        }

    # --------------------------------------------------
    # CLIMATE
    # --------------------------------------------------

    elif intent == "climate":

        return {
            "question": question,
            "parsed_query": parsed_query,
            "location": location,
            "error": (
                "Climate date-range processing "
                "will be added next."
            )
        }

    # --------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------

    else:

        return {
            "question": question,
            "parsed_query": parsed_query,
            "error": (
                "I could not understand "
                "the weather request."
            )
        }

    # --------------------------------------------------
    # FINAL STRUCTURED RESULT
    # --------------------------------------------------

    return {
        "question": question,
        "language": parsed_query[
            "language"
        ],
        "intent": intent,
        "location": location,
        "coordinates": coordinates,
        "weather_data": weather_data,
        "validation": validation,
        "parsed_query": parsed_query,
        "resolved_date": parsed_query.get(
            "resolved_date"
        )
    }


# --------------------------------------------------
# MAIN WEATHERGPT PIPELINE
# --------------------------------------------------

def ask_weathergpt(
    question: str,
    context: dict = None
) -> str:
    """
    Complete WeatherGPT pipeline.

    User question
        ↓
    Groq query understanding
        ↓
    Entity normalization
        ↓
    Conversation context
        ↓
    Intent + entities
        ↓
    Weather tool
        ↓
    Data validation
        ↓
    Groq LLM
        ↓
    Hallucination check
        ↓
    Translation
        ↓
    Final response
    """

    result = process_user_query(
        question,
        context
    )

    # --------------------------------------------------
    # HANDLE BACKEND ERRORS
    # --------------------------------------------------

    if "error" in result:

        error_language = (
            result.get("parsed_query", {})
            .get("language", "en")
        )

        return translate_response(
            result["error"],
            error_language
        )

    weather_data = result.get(
        "weather_data"
    )

    intent = result.get(
        "intent"
    )

    # --------------------------------------------------
    # ALERTS: rendered directly from official provider data
    # (never passed through the LLM, so nothing can be invented)
    # --------------------------------------------------

    if intent == "alert":

        return translate_response(
            format_alert_response(
                weather_data
            ),
            result.get(
                "language",
                "en"
            )
        )

    # --------------------------------------------------
    # GENERATE RESPONSE USING GROQ
    # --------------------------------------------------

    response = generate_llm_response(
        question,
        result
    )

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------

    if not response:

        print(
            "\n[Using rule-based fallback]"
        )

        response = generate_advisory(
            result
        )

    # --------------------------------------------------
    # HALLUCINATION CHECK
    # --------------------------------------------------

    if intent == "current_weather":

        check = check_current_weather_response(
            response,
            weather_data
        )

    elif intent == "forecast":

        check = check_forecast_response(
            response,
            weather_data
        )

    else:

        return response

    # --------------------------------------------------
    # BLOCK UNSAFE RESPONSE
    # --------------------------------------------------

    if not check["safe"]:

        print(
            "\n[Hallucination check failed]"
        )

        fallback_response = generate_advisory(
            result
        )

        return translate_response(
            fallback_response,
            result.get(
                "language",
                "en"
            )
        )

    # --------------------------------------------------
    # TRANSLATION
    # --------------------------------------------------

    language = result.get(
        "language",
        "en"
    )

    translated_response = translate_response(
        response,
        language
    )

    return translated_response


# --------------------------------------------------
# TEST WEATHERGPT
# --------------------------------------------------

if __name__ == "__main__":

    # Start with a clean conversation
    reset_conversation_context()

    questions = [
        "Will it rain tomorrow in Bhopal?",
        "What about evening?",
        "Will it rain there tomorrow morning?",
        "What about Mumbai?",
        "What about tonight?",
        "कल भोपाल में बारिश होगी क्या?",
        "What about afternoon?"
    ]

    for question in questions:

        print(
            "\n========================================"
        )

        print("USER:")

        print(question)

        print(
            "\nWEATHERGPT:"
        )

        print(
            "----------------------------------------"
        )

        answer = ask_weathergpt(
            question
        )

        print(answer)

        print(
            "\nCONTEXT:"
        )

        print(
            CONVERSATION_CONTEXT
        )