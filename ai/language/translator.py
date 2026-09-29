import re


def translate_response(
    response: str,
    language: str
) -> str:
    """
    Translate a WeatherGPT response into
    the requested language.

    Currently supports:
        en -> English
        hi -> Hindi

    This is a rule-based prototype.
    A real translation model/API can be
    connected later.
    """

    # English response does not need translation
    if language == "en":
        return response

    # Hindi translation
    if language == "hi":

        translated = response

        # --------------------------------------------------
        # CURRENT WEATHER HEADING
        # --------------------------------------------------

        translated = re.sub(
            r"Current weather in (.+):",
            r"\1 में वर्तमान मौसम:",
            translated
        )

        # --------------------------------------------------
        # FORECAST HEADING
        # --------------------------------------------------

        translated = re.sub(
            r"Forecast for (.+) on (\d{4}-\d{2}-\d{2}):",
            r"\1 के लिए \2 का मौसम पूर्वानुमान:",
            translated
        )

        # --------------------------------------------------
        # WEATHER VALUES
        # --------------------------------------------------

        translated = translated.replace(
            "Temperature:",
            "तापमान:"
        )

        translated = translated.replace(
            "Feels like:",
            "महसूस हो रहा है:"
        )

        translated = translated.replace(
            "Humidity:",
            "आर्द्रता:"
        )

        translated = translated.replace(
            "Rain:",
            "बारिश:"
        )

        translated = translated.replace(
            "Wind speed:",
            "हवा की गति:"
        )

        translated = translated.replace(
            "Rain probability:",
            "बारिश की संभावना:"
        )

        translated = translated.replace(
            "Expected precipitation:",
            "अपेक्षित वर्षा:"
        )

        # --------------------------------------------------
        # CURRENT WEATHER ADVISORY
        # --------------------------------------------------

        translated = translated.replace(
            "Rain is currently being observed.",
            "वर्तमान में बारिश हो रही है।"
        )

        # --------------------------------------------------
        # FORECAST ADVISORIES
        # --------------------------------------------------

        translated = translated.replace(
            "There is a low chance of rain "
            "based on the available forecast.",
            "उपलब्ध पूर्वानुमान के अनुसार "
            "बारिश की संभावना कम है।"
        )

        translated = translated.replace(
            "There is a moderate chance of rain. "
            "Keep rain protection available.",
            "बारिश की मध्यम संभावना है। "
            "बारिश से बचाव की तैयारी रखें।"
        )

        translated = translated.replace(
            "There is a high chance of rain. "
            "Consider carrying an umbrella.",
            "बारिश की अधिक संभावना है। "
            "छाता साथ रखने पर विचार करें।"
        )

        # --------------------------------------------------
        # COMMON ERROR / STATUS MESSAGES
        # --------------------------------------------------

        translated = translated.replace(
            "Weather data is not available.",
            "मौसम संबंधी डेटा उपलब्ध नहीं है।"
        )

        translated = translated.replace(
            "Forecast data is not available.",
            "मौसम पूर्वानुमान डेटा उपलब्ध नहीं है।"
        )

        translated = translated.replace(
            "Location not detected. "
            "Please specify a city.",
            "स्थान का पता नहीं चला। "
            "कृपया शहर का नाम बताएं।"
        )

        translated = translated.replace(
            "Alert tool is not connected yet.",
            "मौसम चेतावनी सेवा अभी कनेक्ट नहीं की गई है।"
        )

        translated = translated.replace(
            "Time period:",
            "समय अवधि:"
        )

        for english, hindi in {
            "full_day": "पूरा दिन",
            "morning": "सुबह",
            "afternoon": "दोपहर",
            "evening": "शाम",
            "night": "रात"
        }.items():

            translated = translated.replace(
                "समय अवधि: " + english,
                "समय अवधि: " + hindi
            )

        translated = translated.replace(
            "Maximum wind speed:",
            "अधिकतम हवा की गति:"
        )

        translated = translated.replace(
            "Weather alert data is not configured "
            "for this location.",
            "इस स्थान के लिए मौसम चेतावनी डेटा "
            "कॉन्फ़िगर नहीं किया गया है।"
        )

        translated = translated.replace(
            "Weather alert data is currently unavailable "
            "from the provider. Please try again later.",
            "मौसम चेतावनी डेटा प्रदाता से अभी उपलब्ध नहीं है। "
            "कृपया बाद में पुनः प्रयास करें।"
        )

        translated = re.sub(
            r"No active weather warnings for (.+) "
            r"according to IMD\.",
            r"IMD के अनुसार \1 के लिए कोई सक्रिय "
            r"मौसम चेतावनी नहीं है।",
            translated
        )

        translated = re.sub(
            r"Weather alerts for (.+) \(IMD district warnings",
            r"\1 के लिए मौसम चेतावनियाँ (IMD जिला चेतावनियाँ",
            translated
        )

        translated = re.sub(
            r"Weather data for (.+) is not configured yet\.",
            r"\1 के लिए मौसम डेटा अभी उपलब्ध नहीं है।",
            translated
        )

        translated = translated.replace(
            "Forecast data is not available for the "
            "requested time period.",
            "अनुरोधित समय अवधि के लिए पूर्वानुमान डेटा "
            "उपलब्ध नहीं है।"
        )

        translated = translated.replace(
            "I could not understand "
            "the weather request.",
            "मैं मौसम संबंधी अनुरोध को समझ नहीं सका।"
        )

        return translated

    # --------------------------------------------------
    # UNSUPPORTED LANGUAGE
    # --------------------------------------------------

    return response


# --------------------------------------------------
# TEST TRANSLATOR
# --------------------------------------------------

if __name__ == "__main__":

    current_weather_response = (
        "Current weather in Bhopal:\n"
        "Temperature: 24.1°C\n"
        "Feels like: 27.1°C\n"
        "Humidity: 80%\n"
        "Rain: 0.0 mm\n"
        "Wind speed: 7.5 km/h"
    )

    forecast_response = (
        "Forecast for Bhopal on 2026-09-29:\n"
        "Temperature: 21.9°C – 30.7°C\n"
        "Rain probability: 7%\n"
        "Expected precipitation: 0.4 mm\n\n"
        "There is a low chance of rain "
        "based on the available forecast."
    )

    print("\n========================================")
    print("CURRENT WEATHER - ENGLISH")
    print("========================================")
    print(current_weather_response)

    print("\n========================================")
    print("CURRENT WEATHER - HINDI")
    print("========================================")
    print(
        translate_response(
            current_weather_response,
            "hi"
        )
    )

    print("\n========================================")
    print("FORECAST - ENGLISH")
    print("========================================")
    print(forecast_response)

    print("\n========================================")
    print("FORECAST - HINDI")
    print("========================================")
    print(
        translate_response(
            forecast_response,
            "hi"
        )
    )