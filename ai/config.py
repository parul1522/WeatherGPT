"""Single source of configuration for the WeatherGPT AI package.

All AI-related settings come from environment variables. A ``.env`` file in the
project root is loaded automatically when ``python-dotenv`` is installed;
variables already set in the real environment always win.

Variables
---------
GROQ_API_KEY      Groq API key. If unset, the pipeline runs without the LLM
                  (rule-based query understanding + rule-based responses).
GROQ_MODEL        Groq model id (default: ``openai/gpt-oss-20b``).
IMD_DISTRICT_IDS  Optional JSON object mapping city name -> IMD district
                  ``obj_id``, e.g. ``{"Bhopal": 123}``. Only verified IDs
                  belong here. Cities without an ID report "not configured".
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

try:  # optional: python-dotenv is listed in requirements.txt
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - only when dotenv is not installed
    pass

DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"


def get_groq_api_key():
    """Return the Groq API key, or None when not configured."""
    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    return key or None


def get_groq_model() -> str:
    """Return the configured Groq model id."""
    return (os.environ.get("GROQ_MODEL") or "").strip() or DEFAULT_GROQ_MODEL


def get_imd_district_ids() -> dict:
    """Parse ``IMD_DISTRICT_IDS`` into ``{city: {"obj_id": int}}``.

    Malformed input is ignored (logged) so the alert tool reports
    ``not_configured`` instead of guessing.
    """
    raw = (os.environ.get("IMD_DISTRICT_IDS") or "").strip()
    if not raw:
        return {}

    try:
        data = json.loads(raw)
    except ValueError:
        logger.warning("IMD_DISTRICT_IDS is not valid JSON; ignoring it.")
        return {}

    if not isinstance(data, dict):
        logger.warning("IMD_DISTRICT_IDS must be a JSON object; ignoring it.")
        return {}

    districts = {}
    for city, value in data.items():
        obj_id = value.get("obj_id") if isinstance(value, dict) else value
        try:
            districts[str(city)] = {"obj_id": int(obj_id)}
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid IMD obj_id for %s.", city)
    return districts
