import re


def detect_language(text: str) -> str:
    """
    Detect the language of the user's message.

    Returns:
        "hi" for Hindi
        "en" for English
    """

    # Hindi Unicode range
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"

    return "en"


def detect_intent(text: str) -> str:
    """
    Detect the main weather-related intent.
    """

    text_lower = text.lower()

    # Current weather
    current_keywords = [
        "weather",
        "temperature",
        "current",
        "right now",
        "abhi",
        "mausam",
        "तापमान",
        "मौसम"
    ]

    # Forecast
    forecast_keywords = [
        "tomorrow",
        "today",
        "forecast",
        "rain",
        "raining",
        "बारिश",
        "कल",
        "बरसात"
    ]

    # Alerts
    alert_keywords = [
        "alert",
        "warning",
        "cyclone",
        "flood",
        "storm",
        "चेतावनी",
        "बाढ़",
        "तूफान"
    ]

    # Climate / historical
    climate_keywords = [
        "historical",
        "history",
        "climate",
        "trend",
        "past",
        "इतिहास",
        "जलवायु",
        "रुझान"
    ]

    if any(keyword in text_lower for keyword in alert_keywords):
        return "alert"

    if any(keyword in text_lower for keyword in climate_keywords):
        return "climate"

    if any(keyword in text_lower for keyword in forecast_keywords):
        return "forecast"

    if any(keyword in text_lower for keyword in current_keywords):
        return "current_weather"

    return "unknown"


def extract_location(text: str) -> str | None:
    """
    Extract a known location from the user's message.

    Supports English and common Hindi city names.
    """

    locations = {
        "Bhopal": ["bhopal", "भोपाल"],
        "Delhi": ["delhi", "दिल्ली"],
        "Mumbai": ["mumbai", "मुंबई"],
        "Indore": ["indore", "इंदौर"],
        "Pune": ["pune", "पुणे"],
        "Bengaluru": ["bengaluru", "bangalore", "बेंगलुरु", "बैंगलोर"],
        "Kolkata": ["kolkata", "calcutta", "कोलकाता"],
        "Chennai": ["chennai", "चेन्नई"],
        "Hyderabad": ["hyderabad", "हैदराबाद"],
        "Jaipur": ["jaipur", "जयपुर"],
        "Lucknow": ["lucknow", "लखनऊ"],
        "Ahmedabad": ["ahmedabad", "अहमदाबाद"]
    }

    text_lower = text.lower()

    for city, names in locations.items():
        for name in names:
            if name.lower() in text_lower:
                return city

    return None


_NOT_A_PLACE = {
    "the", "a", "an", "my", "our", "your", "there", "here", "this", "that",
    "today", "tomorrow", "tonight", "morning", "afternoon", "evening",
    "night", "general", "case", "india", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday"
}


def extract_unrecognized_location(text: str) -> str | None:
    """
    Detect an explicitly written place name that is not one of the
    supported cities, e.g. "weather in Atlantis".

    Only a capitalised word directly after "in", "at" or "for" is
    considered, so ordinary phrases ("in the evening") are ignored.
    Returning the name lets the pipeline say the location is not
    supported instead of silently answering for a previous city.
    """

    match = re.search(
        r"\b(?:in|at|for)\s+([A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+)?)",
        text
    )

    if not match:
        return None

    name = match.group(1).strip()

    if name.split()[0].lower() in _NOT_A_PLACE:
        return None

    return name


def parse_user_query(text: str) -> dict:
    """
    Convert a natural-language weather question
    into structured information.
    """

    return {
        "text": text,
        "language": detect_language(text),
        "intent": detect_intent(text),
        "location": (
            extract_location(text)
            or extract_unrecognized_location(text)
        )
    }


# Test the detector
if __name__ == "__main__":

    test_questions = [
        "What's the weather in Bhopal?",
        "Will it rain tomorrow in Bhopal?",
        "कल भोपाल में बारिश होगी क्या?",
        "Is there any flood warning in Delhi?",
        "Show historical weather for Mumbai"
    ]

    for question in test_questions:
        print("\nQuestion:", question)
        print(parse_user_query(question))