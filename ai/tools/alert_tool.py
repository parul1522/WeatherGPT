import requests

from ai.config import get_imd_district_ids


# --------------------------------------------------
# IMD DISTRICT CONFIGURATION
# --------------------------------------------------
#
# IMD's district warning API requires an obj_id.
#
# Do NOT invent these IDs.
# Add the verified IMD district obj_id when available.
#
# Example:
#
# "Bhopal": {
#     "obj_id": 573
# }
#
# The API documentation shows:
#
# https://mausam.imd.gov.in/api/warnings_district_api.php?id=573
#
# where 573 is the district obj_id.
#
# --------------------------------------------------

DISTRICT_IDS = {
    # Add verified IMD district IDs here, or set the
    # IMD_DISTRICT_IDS environment variable (JSON), e.g.
    #   IMD_DISTRICT_IDS={"Bhopal": 123}
    # Entries in the environment override this dict.
    #
    # "Bhopal": {
    #     "obj_id": 123
    # },
    #
    # "Delhi": {
    #     "obj_id": 456
    # }
}


# --------------------------------------------------
# IMD WARNING CODE DEFINITIONS
# --------------------------------------------------

WARNING_CODES = {
    1: "No Warning",
    2: "Heavy Rain",
    3: "Heavy Snow",
    4: "Thunderstorm & Lightning, Squall etc",
    5: "Hailstorm",
    6: "Dust Storm",
    7: "Dust Raising Winds",
    8: "Strong Surface Winds",
    9: "Heat Wave",
    10: "Hot Day",
    11: "Warm Night",
    12: "Cold Wave",
    13: "Cold Day",
    14: "Ground Frost",
    15: "Fog",
    16: "Very Heavy Rain",
    17: "Extremely Heavy Rain"
}


# --------------------------------------------------
# IMD COLOR CODE DEFINITIONS
# --------------------------------------------------

COLOR_CODES = {
    1: "Red",
    2: "Orange",
    3: "Yellow",
    4: "Green"
}


# --------------------------------------------------
# PARSE WARNING CODES
# --------------------------------------------------

def parse_warning_codes(
    warning_value
) -> list:
    """
    Convert IMD warning code values into a list.

    IMD may return multiple warning codes separated
    by commas.

    Example:

        "2,4"

    becomes:

        [2, 4]
    """

    if warning_value is None:
        return []

    if isinstance(
        warning_value,
        int
    ):
        return [warning_value]

    value = str(
        warning_value
    ).strip()

    if not value:
        return []

    codes = []

    for item in value.split(","):

        item = item.strip()

        try:

            code = int(item)

            codes.append(code)

        except ValueError:

            continue

    return codes


# --------------------------------------------------
# PARSE COLOR CODE
# --------------------------------------------------

def parse_color_code(
    color_value
) -> int | None:
    """
    Convert an IMD color value into an integer.
    """

    if color_value is None:
        return None

    try:

        return int(
            str(color_value).strip()
        )

    except (
        TypeError,
        ValueError
    ):

        return None


# --------------------------------------------------
# BUILD WARNING ENTRY
# --------------------------------------------------

def build_warning_entry(
    day_number: int,
    warning_value,
    color_value,
    issue_date: str,
    district: str
) -> dict:
    """
    Convert one IMD day warning into a standardized
    WeatherGPT warning dictionary.
    """

    warning_codes = parse_warning_codes(
        warning_value
    )

    color_code = parse_color_code(
        color_value
    )

    warning_names = []

    for code in warning_codes:

        warning_names.append(
            WARNING_CODES.get(
                code,
                f"Unknown warning code {code}"
            )
        )

    # --------------------------------------------------
    # NO WARNING
    # --------------------------------------------------

    if (
        not warning_codes
        or warning_codes == [1]
    ):

        warning_names = [
            "No Warning"
        ]

    return {
        "day": day_number,
        "district": district,
        "issue_date": issue_date,
        "warning_codes": warning_codes,
        "warnings": warning_names,
        "color_code": color_code,
        "color": (
            COLOR_CODES.get(
                color_code
            )
            if color_code is not None
            else None
        )
    }


# --------------------------------------------------
# FETCH IMD DISTRICT WARNINGS
# --------------------------------------------------

def get_weather_alerts(
    latitude: float,
    longitude: float,
    location: str = None
) -> dict:
    """
    Retrieve official IMD district weather warnings.

    Args:
        latitude:
            Location latitude.

        longitude:
            Location longitude.

        location:
            City/district name used to identify the
            configured IMD district.

    Returns:
        Standardized weather-alert dictionary.

    Notes:
        IMD's documented district warning API requires
        a district obj_id.

        If an obj_id has not been configured, this
        function safely returns a not_configured status
        instead of inventing alert information.
    """

    # --------------------------------------------------
    # LOCATION REQUIRED
    # --------------------------------------------------

    if not location:

        return {
            "latitude": latitude,
            "longitude": longitude,
            "location": None,
            "alerts": [],
            "source": "India Meteorological Department",
            "status": "location_required"
        }

    # --------------------------------------------------
    # FIND DISTRICT ID
    # --------------------------------------------------

    district_config = {
        **DISTRICT_IDS,
        **get_imd_district_ids()
    }.get(
        location
    )

    if not district_config:

        return {
            "latitude": latitude,
            "longitude": longitude,
            "location": location,
            "alerts": [],
            "source": "India Meteorological Department",
            "status": "not_configured",
            "message": (
                "IMD district obj_id is not configured "
                "for this location."
            )
        }

    obj_id = district_config.get(
        "obj_id"
    )

    if obj_id is None:

        return {
            "latitude": latitude,
            "longitude": longitude,
            "location": location,
            "alerts": [],
            "source": "India Meteorological Department",
            "status": "not_configured",
            "message": (
                "IMD district obj_id is missing."
            )
        }

    # --------------------------------------------------
    # IMD API
    # --------------------------------------------------

    url = (
        "https://mausam.imd.gov.in/"
        "api/warnings_district_api.php"
    )

    params = {
        "id": obj_id
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException as error:

        return {
            "latitude": latitude,
            "longitude": longitude,
            "location": location,
            "alerts": [],
            "source": "India Meteorological Department",
            "status": "api_error",
            "error": str(error)
        }

    except ValueError as error:

        return {
            "latitude": latitude,
            "longitude": longitude,
            "location": location,
            "alerts": [],
            "source": "India Meteorological Department",
            "status": "invalid_response",
            "error": str(error)
        }

    # --------------------------------------------------
    # NORMALIZE RESPONSE
    # --------------------------------------------------

    if isinstance(
        data,
        dict
    ):

        raw_data = data

    elif isinstance(
        data,
        list
    ) and data:

        raw_data = data[0]

    else:

        return {
            "latitude": latitude,
            "longitude": longitude,
            "location": location,
            "alerts": [],
            "source": "India Meteorological Department",
            "status": "empty_response"
        }

    issue_date = (
        raw_data.get("Date")
        or raw_data.get("date")
    )

    district = (
        raw_data.get("District")
        or raw_data.get("district")
        or location
    )

    alerts = []

    # --------------------------------------------------
    # DAY 1 TO DAY 5
    # --------------------------------------------------

    for day_number in range(
        1,
        6
    ):

        warning_value = (
            raw_data.get(
                f"Day_{day_number}"
            )
            or raw_data.get(
                f"day_{day_number}"
            )
        )

        color_value = (
            raw_data.get(
                f"Day{day_number}_Color"
            )
            or raw_data.get(
                f"day{day_number}_Color"
            )
        )

        alert = build_warning_entry(
            day_number=day_number,
            warning_value=warning_value,
            color_value=color_value,
            issue_date=issue_date,
            district=district
        )

        alerts.append(
            alert
        )

    # --------------------------------------------------
    # RETURN STANDARDIZED RESULT
    # --------------------------------------------------

    return {
        "latitude": latitude,
        "longitude": longitude,
        "location": location,
        "district": district,
        "issue_date": issue_date,
        "alerts": alerts,
        "source": (
            "India Meteorological Department "
            "District Warning API"
        ),
        "status": "available"
    }


# --------------------------------------------------
# TEST THE ALERT TOOL
# --------------------------------------------------

if __name__ == "__main__":

    alerts = get_weather_alerts(
        latitude=23.2599,
        longitude=77.4126,
        location="Bhopal"
    )

    print(
        "\n========================================"
    )

    print(
        "IMD WEATHER ALERT TOOL TEST"
    )

    print(
        "========================================"
    )

    print(
        "\nResult:"
    )

    print(
        alerts
    )