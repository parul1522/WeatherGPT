"""AI service: the single entry point from the backend into the WeatherGPT AI
pipeline (``ai.agents.weather_agent.ask_weathergpt``).

Responsibilities kept here (and out of the routers):

* per-conversation context, so follow-up questions inherit location, date and
  time range without different users sharing state;
* turning unexpected pipeline failures into one controlled error type.

This module deliberately has no FastAPI/pydantic imports so it can be tested
without the web stack.
"""

import logging
import threading
import time
import uuid

from ai.agents.weather_agent import ask_weathergpt

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_SESSIONS = 1000


class AIServiceError(Exception):
    """The AI pipeline failed unexpectedly."""


class _Session:
    def __init__(self):
        self.context = {
            "intent": None,
            "location": None,
            "date": None,
            "time_range": None,
            "weather_parameter": None,
            "language": "en",
        }
        self.lock = threading.Lock()
        self.last_used = time.monotonic()


_sessions: dict = {}
_sessions_lock = threading.Lock()


def _evict_locked(now: float) -> None:
    expired = [
        sid for sid, s in _sessions.items()
        if now - s.last_used > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        del _sessions[sid]

    while len(_sessions) >= MAX_SESSIONS:
        oldest = min(_sessions, key=lambda sid: _sessions[sid].last_used)
        del _sessions[oldest]


def _get_session(session_id: str | None):
    """Return (session_id, session); creates a session when needed."""

    now = time.monotonic()

    with _sessions_lock:
        if session_id and session_id in _sessions:
            session = _sessions[session_id]
        else:
            _evict_locked(now)
            session_id = session_id or uuid.uuid4().hex
            session = _Session()
            _sessions[session_id] = session
        session.last_used = now

    return session_id, session


def reset_sessions() -> None:
    """Forget every conversation (used by tests)."""

    with _sessions_lock:
        _sessions.clear()


def answer_chat(message: str, session_id: str | None = None) -> dict:
    """Run one chat turn through the AI pipeline.

    Returns ``{"reply", "lang", "session_id"}``. ``lang`` is the language the
    pipeline detected and answered in.
    """

    session_id, session = _get_session(session_id)

    try:
        with session.lock:
            reply = ask_weathergpt(message, session.context)
            lang = session.context.get("language") or "en"
    except Exception as error:  # noqa: BLE001 - reported, never swallowed
        logger.exception("WeatherGPT pipeline failed")
        raise AIServiceError(
            "WeatherGPT could not process this request."
        ) from error

    return {"reply": reply, "lang": lang, "session_id": session_id}
