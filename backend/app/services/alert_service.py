"""Alert service: official IMD warnings via the AI alert tool.

The tool reports one of: available, not_configured, location_required,
api_error, invalid_response, empty_response. ``message`` is rendered from that
status by the same formatter the chat pipeline uses, so REST and chat always
say the same thing. Nothing is invented: "no active alerts" is only reported
when IMD was actually queried and returned no warnings.
"""

from ai.agents.alert_agent import format_alert_response
from ai.tools.alert_tool import get_weather_alerts


def get_alerts(lat: float, lon: float, location: str | None = None) -> dict:
    data = get_weather_alerts(lat, lon, location)

    return {
        "module": "alerts",
        "location": {
            "latitude": lat,
            "longitude": lon,
            "name": location,
        },
        "status": data.get("status"),
        "district": data.get("district"),
        "issue_date": data.get("issue_date"),
        "source": data.get("source"),
        "alerts": data.get("alerts", []),
        "message": format_alert_response(data),
    }
