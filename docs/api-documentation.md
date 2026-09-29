# API Documentation

Interactive docs: http://localhost:8000/docs

| Method | Path | Description |
|---|---|---|
| GET | /health | Health check |
| POST | /api/chat | Chat with WeatherGPT (AI pipeline) |
| GET | /api/weather | Daily forecast (lat, lon, days) |
| GET | /api/alerts | Official IMD alerts (lat, lon, location) |
| GET | /api/climate | Historical data (lat, lon, start_date, end_date) |
| GET | /api/location | Location lookup (placeholder) |

## POST /api/chat

Request: `{"message": "...", "lang": "en", "session_id": null}`
Response: `{"reply": "...", "lang": "en|hi", "session_id": "..."}`

`lang` in the request is informational; the reply language is detected from the
message. Send the returned `session_id` with the next message so follow-ups
("What about evening?") inherit location/date/time. Without it every message
is a fresh conversation. Pipeline failure -> HTTP 503.

## GET /api/alerts

Returns `status` = `available | not_configured | location_required | api_error |
invalid_response | empty_response`, the IMD `alerts`, and a `message`. "No active
weather warnings" is only returned when IMD was queried and reported none.
