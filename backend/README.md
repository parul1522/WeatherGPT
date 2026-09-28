# WeatherGPT API (Backend – Member 2)

FastAPI backend for **WeatherGPT**, an AI-powered conversational weather assistant (Smart India Hackathon).
It serves the React Native app with normalized weather, forecast, historical climate, geocoding, alert and
chat APIs.

---

## 1. Project overview

| Feature | Endpoint | Data source |
|---|---|---|
| Current weather | `GET /api/v1/weather/current` | Open-Meteo Forecast API |
| 1–7 day forecast (daily + hourly) | `GET /api/v1/weather/forecast` | Open-Meteo Forecast API |
| Natural-language chat | `POST /api/v1/chat` | Groq (default; OpenAI/Gemini optional) + the APIs above |
| Place search | `GET /api/v1/location/geocode` | Open-Meteo Geocoding API |
| Alerts & advisories | `GET /api/v1/alerts` | Official provider (none yet) + rule-based advisories |
| Historical weather | `GET /api/v1/climate/history` | Open-Meteo Historical (archive) API |
| Health check | `GET /health` | – |

Two rules the whole codebase is built around:

1. **The LLM never supplies weather values.** It only classifies the question and phrases an answer from data the backend fetched.
2. **Nothing app-generated is presented as an official warning.** Advisories carry `"is_official": false`; official alerts only come from an official provider.

## 2. Architecture

```
React Native app
      │  HTTPS / JSON  (/api/v1/...)
      ▼
┌───────────── FastAPI ─────────────┐
│ api/        thin routes            │
│   │ Depends(...)                   │
│ services/   business logic         │
│   ├─ weather_service ─► WeatherProvider ─► OpenMeteoProvider ─► Open-Meteo
│   ├─ geocoding_service ─────────────────────────────────────► Open-Meteo Geocoding
│   ├─ climate_service ───────────────────────────────────────► Open-Meteo Archive
│   ├─ alert_service ─► AlertProvider (none yet; IMD later) + advisories
│   ├─ ai_service ─► AIService ─► GroqAIService | OpenAIAIService | GeminiAIService
│   ├─ chat_service  (orchestrates the chat flow)
│   └─ cache         (in-memory TTL; Redis-ready interface)
│ database/   SQLAlchemy async + CRUD ─► PostgreSQL
└────────────────────────────────────┘
```

**Chat flow**

```
question ─► AI: extract intent (JSON, validated by Pydantic)
         ─► backend: resolve location (named place → geocode, else device GPS)
         ─► backend: fetch only the data needed (current / forecast / alerts)
         ─► AI: write the answer using ONLY that verified data
         ─► response (+ conversation saved to DB)
```
If the AI or a weather provider fails, the API returns an error. It never falls back to a guessed answer.

**Caching.** Current weather: in-memory cache (10 min) → recent DB row (10 min) → provider. Forecast: in-memory (30 min).
Geocoding and historical data: in-memory (24 h). Coordinates are rounded to ~1 km for cache keys.

**Degraded mode.** If PostgreSQL is down, weather endpoints still work; saving data fails and is logged.

## 3. Folder structure

The team repo keeps `docker-compose.yml` and `.env.example` at the repo root (`WeatherGPT/`), not in `backend/`.

```
backend/
├── app/
│   ├── main.py                  # app, CORS, error handlers, router registration, /health
│   ├── api/
│   │   ├── deps.py              # dependency wiring (services, location/date parsing)
│   │   ├── chat.py  weather.py  alerts.py  climate.py  location.py
│   ├── core/
│   │   ├── config.py            # Pydantic Settings (env vars)
│   │   ├── security.py          # optional X-API-Key check
│   │   └── exceptions.py        # error classes → HTTP status + error code
│   ├── database/
│   │   ├── connection.py        # engine, session factory, get_db, init_db
│   │   └── crud.py              # all DB reads/writes
│   ├── models/                  # SQLAlchemy tables: user.py (users, conversations), weather.py, alert.py
│   ├── schemas/                 # Pydantic: chat, weather, alert, climate, location
│   └── services/                # weather, ai, alert, climate, geocoding, chat, cache, http_client
├── tests/                       # pytest, all external APIs mocked
├── requirements.txt  Dockerfile  .dockerignore  pytest.ini  README.md
```

## 4. Requirements

- Python 3.11+ (Docker image uses 3.12)
- PostgreSQL 14+ (or Docker)
- A Groq API key for `/api/v1/chat` (all other endpoints work without one)

## 5. Environment setup

```bash
# from the repo root (WeatherGPT/)
cp .env.example .env               # Windows: copy .env.example .env   → put your Groq key in LLM_API_KEY
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

The backend reads the shared `WeatherGPT/.env` automatically (and `backend/.env` if you create one, which takes priority).

## 6. `.env` configuration

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://weathergpt:weathergpt@db:5432/weathergpt` | `postgresql://` is auto-converted to `+asyncpg`. Use `localhost` instead of `db` when running outside Docker |
| `AI_PROVIDER` | `groq` | `groq`, `openai`, `gemini` or `none` |
| `LLM_API_KEY` (or `GROQ_API_KEY`) / `GROQ_MODEL` | – / `openai/gpt-oss-20b` | Groq key and model |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | – / `gemini-2.5-flash` | needed only if `AI_PROVIDER=gemini` |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | – / `gpt-4o-mini` | needed only if `AI_PROVIDER=openai` |
| `WEATHER_API_BASE_URL` | `https://api.open-meteo.com/v1` | |
| `CLIMATE_API_BASE_URL` | `https://archive-api.open-meteo.com/v1` | |
| `GEOCODING_API_BASE_URL` | `https://geocoding-api.open-meteo.com/v1` | |
| `ALERT_PROVIDER` | `none` | official alert feed (only `none` until IMD is integrated) |
| `CURRENT_WEATHER_TTL_SECONDS` / `FORECAST_TTL_SECONDS` | `600` / `1800` | `0` disables |
| `CORS_ORIGINS` | `*` | comma-separated list in production |
| `API_KEY` | empty | if set, clients must send `X-API-Key` |
| `ENVIRONMENT`, `LOG_LEVEL` | `development`, `INFO` | |

Model names change over time. If Groq returns "model not found" or "decommissioned", pick a current one from https://console.groq.com/docs/models and set `GROQ_MODEL`. The intent step uses JSON mode, which Groq supports on the `openai/gpt-oss-*` models; `openai/gpt-oss-120b` is a stronger but slower option.
`REDIS_URL` and `SECRET_KEY` in the root `.env` are not used by the backend yet (it caches in memory; JWT auth is future work).
**Never commit `.env`** (it is in `.gitignore`).

## 7. Local installation

See section 5. Then make sure PostgreSQL is running (section 8) and start the API (section 10).

## 8. PostgreSQL setup

Easiest: run only the database from Compose (from the repo root):

```bash
docker compose up -d db
```
then set `DATABASE_URL=postgresql://weathergpt:weathergpt@localhost:5432/weathergpt` in `.env` for local runs.

Or with a local install:

```bash
psql -U postgres -c "CREATE USER weathergpt WITH PASSWORD 'weathergpt';"
psql -U postgres -c "CREATE DATABASE weathergpt OWNER weathergpt;"
```

Tables (`users`, `conversations`, `weather_observations`, `alerts`) are created automatically on startup.
When the schema starts changing between releases, add Alembic migrations.

## 9. Docker setup

From the repo root (`WeatherGPT/`):

```bash
cp .env.example .env          # add your Groq key to LLM_API_KEY
docker compose up --build     # backend + db + redis; API on http://localhost:8000
docker compose logs -f backend
docker compose down           # stop (add -v to also delete the database volume)
```

The backend waits for Postgres to be healthy, and also retries its database setup for ~10 seconds on startup.

## 10. Running the API

```bash
uvicorn app.main:app --reload --port 8000
```

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: `curl http://localhost:8000/health` → `{"status":"ok","service":"WeatherGPT API"}`

To reach it from a phone on the same Wi-Fi: `uvicorn app.main:app --host 0.0.0.0 --port 8000` and use your computer's LAN IP.

## 11. API endpoints

All data endpoints are under `/api/v1`. Location can be given **either** as `latitude` + `longitude`
(optionally `location_name` to echo back) **or** as `query` (a place name that the backend geocodes).

| Method | Path | Parameters |
|---|---|---|
| GET | `/health` | – |
| GET | `/api/v1/weather/current` | location |
| GET | `/api/v1/weather/forecast` | location, `days` (1–7, default 3), `include_hourly` (default true) |
| POST | `/api/v1/chat` | JSON body (below) |
| GET | `/api/v1/location/geocode` | `query` (2–100 chars; `"Aurangabad, Bihar"` disambiguates), `language` |
| GET | `/api/v1/alerts` | location, `include_advisories` (default false) |
| GET | `/api/v1/climate/history` | location, `start_date`, `end_date` (YYYY-MM-DD, ≤366 days, not in the future, ≥1940) |

### Response conventions (frontend contract)

- Field names are `snake_case`.
- Timestamps are ISO 8601 with offset. `updated_at` / `generated_at` are UTC (`Z`); forecast `time`, `sunrise`, `sunset` are in the location's local time (e.g. `+05:30`) and `timezone` gives the IANA name.
- Units are in each response's `units` object: °C, %, km/h, mm, degrees.
- Every data response includes `source`. Missing provider values are `null`, never invented.
- `weather_code` is a WMO code; `weather_description` is a ready-to-show English label.
- **Errors** always look like:

```json
{"error": {"code": "INVALID_COORDINATES", "message": "Invalid coordinates: latitude input should be less than or equal to 90", "details": [{"field": "latitude", "message": "Input should be less than or equal to 90"}]}}
```

| HTTP | `error.code` | Meaning |
|---|---|---|
| 400 | `INVALID_REQUEST`, `INVALID_COORDINATES`, `INVALID_DATE_RANGE`, `LOCATION_REQUIRED` | bad input; show the message / ask for location |
| 401 | `INVALID_API_KEY` | missing/wrong `X-API-Key` (only when `API_KEY` is set) |
| 404 | `LOCATION_NOT_FOUND` | place name not found |
| 502 | `WEATHER_PROVIDER_UNAVAILABLE`, `GEOCODING_PROVIDER_UNAVAILABLE`, `AI_INVALID_RESPONSE` | upstream problem; offer retry |
| 503 | `AI_SERVICE_UNAVAILABLE`, `AI_SERVICE_NOT_CONFIGURED` | chat unavailable; weather screens still work |
| 500 | `INTERNAL_ERROR` | unexpected; details only in server logs |

## 12. Example requests

```bash
# Current weather by coordinates
curl "http://localhost:8000/api/v1/weather/current?latitude=23.2599&longitude=77.4126&location_name=Bhopal"

# Current weather by place name
curl "http://localhost:8000/api/v1/weather/current?query=Indore"

# 3-day forecast, daily only
curl "http://localhost:8000/api/v1/weather/forecast?latitude=23.2599&longitude=77.4126&days=3&include_hourly=false"

# Chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Will it rain tomorrow in Bhopal?", "language": "en", "latitude": null, "longitude": null}'

# Chat in Hindi using device location
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "क्या आज बारिश होगी?", "language": "hi", "latitude": 23.2599, "longitude": 77.4126, "session_id": "device-123"}'

# Geocode
curl "http://localhost:8000/api/v1/location/geocode?query=Bhopal"

# Alerts (+ app advisories)
curl "http://localhost:8000/api/v1/alerts?latitude=23.2599&longitude=77.4126&include_advisories=true"

# Historical weather
curl "http://localhost:8000/api/v1/climate/history?latitude=23.2599&longitude=77.4126&start_date=2025-06-01&end_date=2025-09-30"

# When API_KEY is set, add:  -H "X-API-Key: <your key>"
```

## 13. Example responses

Values below are illustrative; real values come from the providers.

**Current weather**
```json
{
  "location": {"name": "Bhopal", "latitude": 23.2599, "longitude": 77.4126, "country": null, "state": null},
  "current": {"temperature": 28.0, "feels_like": 31.2, "humidity": 72, "wind_speed": 18.0, "wind_direction": 240,
              "precipitation": 0.0, "weather_code": 2, "weather_description": "Partly cloudy"},
  "units": {"temperature": "°C", "humidity": "%", "wind_speed": "km/h", "wind_direction": "°", "precipitation": "mm", "precipitation_probability": "%"},
  "source": "Open-Meteo",
  "updated_at": "2026-09-28T18:00:00Z"
}
```

**Forecast** (trimmed)
```json
{
  "location": {"name": "Bhopal", "latitude": 23.2599, "longitude": 77.4126, "country": null, "state": null},
  "timezone": "Asia/Kolkata",
  "days": 3,
  "daily": [{"date": "2026-09-28", "weather_code": 61, "weather_description": "Slight rain", "temperature_max": 31.5,
             "temperature_min": 22.1, "precipitation_sum": 3.2, "precipitation_probability_max": 80, "wind_speed_max": 14.0,
             "sunrise": "2026-09-28T06:10:00+05:30", "sunset": "2026-09-28T18:05:00+05:30"}],
  "hourly": [{"time": "2026-09-28T00:00:00+05:30", "temperature": 25.0, "humidity": 80, "precipitation": 0.2,
              "precipitation_probability": 60, "weather_code": 61, "weather_description": "Slight rain", "wind_speed": 10.0}],
  "units": {"temperature": "°C", "humidity": "%", "wind_speed": "km/h", "wind_direction": "°", "precipitation": "mm", "precipitation_probability": "%"},
  "source": "Open-Meteo",
  "updated_at": "2026-09-28T18:02:11Z"
}
```

**Chat**
```json
{
  "answer": "Light rain is likely in Bhopal tomorrow, with about 3.2 mm expected and an 80% chance of rain.",
  "language": "en",
  "intent": "forecast",
  "location": {"name": "Bhopal", "latitude": 23.2547, "longitude": 77.4029, "country": "India", "state": "Madhya Pradesh"},
  "data_used": {"weather": false, "forecast": true, "alerts": false},
  "sources": ["Open-Meteo"],
  "generated_at": "2026-09-28T18:02:13Z"
}
```

**Geocode**
```json
{"name": "Bhopal", "latitude": 23.2547, "longitude": 77.4029, "country": "India", "state": "Madhya Pradesh"}
```

**Alerts** (no official provider configured)
```json
{
  "location": {"name": null, "latitude": 23.2599, "longitude": 77.4126, "country": null, "state": null},
  "alerts": [],
  "advisories": [
    {"advisory_type": "heavy_rain", "level": "moderate", "title": "Heavy rain possible",
     "description": "Forecast rainfall of 72.4 mm on 2026-09-29.", "date": "2026-09-29",
     "basis": "Derived by WeatherGPT from Open-Meteo forecast data. Not an official warning.", "is_official": false}
  ],
  "source": null,
  "message": "No alert provider configured.",
  "generated_at": "2026-09-28T18:02:15Z"
}
```
(`advisories` is `[]` unless `include_advisories=true`.)

**Climate history** (trimmed)
```json
{
  "location": {"name": null, "latitude": 23.2599, "longitude": 77.4126, "country": null, "state": null},
  "start_date": "2025-06-01", "end_date": "2025-09-30",
  "daily": [{"date": "2025-06-01", "temperature_max": 41.2, "temperature_min": 29.0, "temperature_mean": 34.6, "precipitation_sum": 0.0, "wind_speed_max": 21.3}],
  "monthly": [{"month": "2025-06", "days_with_data": 30, "temperature_mean": 31.4, "temperature_max": 43.0,
               "temperature_min": 23.1, "precipitation_total": 180.2, "rainy_days": 11}],
  "summary": {"days_with_data": 122, "temperature_mean": 28.1, "temperature_max": 43.0, "temperature_min": 21.0, "precipitation_total": 1040.5, "rainy_days": 58},
  "units": {"temperature": "°C", "precipitation": "mm", "wind_speed": "km/h"},
  "source": "Open-Meteo Historical",
  "generated_at": "2026-09-28T18:02:20Z"
}
```

## 14. Running tests

```bash
pytest            # or: pytest -v
```

Run from `backend/`. Tests use a temporary SQLite database and mock every external API (Open-Meteo, geocoding, archive, Groq/OpenAI/Gemini)
through `httpx.MockTransport` in `tests/conftest.py`, so they need no network, keys or PostgreSQL.

## 15. Getting API keys

- **Open-Meteo**: no key. Free for non-commercial use with fair-use limits; for commercial use, get an API key plan from open-meteo.com.
- **Groq** (default): create a key at https://console.groq.com/keys → set `LLM_API_KEY=gsk_...` (and `AI_PROVIDER=groq`, the default). Free tier has rate limits; hitting them returns `503` with a "rate limit" message.
- **Gemini** (optional): create a key at https://aistudio.google.com/app/apikey → set `AI_PROVIDER=gemini`, `GEMINI_API_KEY=...`.
- **OpenAI** (optional): create a key at https://platform.openai.com/api-keys → set `AI_PROVIDER=openai`, `OPENAI_API_KEY=...`.

Keys go only in `.env` (local) or your hosting provider's secret settings. Never in code or the mobile app.

## 16. Troubleshooting

| Symptom | Fix |
|---|---|
| Log: `Database initialisation failed (ConnectionRefusedError)` | Start Postgres (`docker compose up -d db`) and check `DATABASE_URL` (`db` inside Docker, `localhost` outside), then restart the API |
| Log: `socket.gaierror` / name `db` not found | You are running outside Docker with the Docker `DATABASE_URL`; change `@db:` to `@localhost:` |
| `AI_SERVICE_NOT_CONFIGURED` | Set `AI_PROVIDER` and the matching key in `.env`, restart |
| `AI_SERVICE_UNAVAILABLE` with 401 in logs | Wrong Groq key in `LLM_API_KEY` |
| `AI_SERVICE_UNAVAILABLE` with 404/400 in logs | `GROQ_MODEL` retired or not supporting JSON mode: pick a current `openai/gpt-oss-*` model |
| `WEATHER_PROVIDER_UNAVAILABLE` | Check internet access; Open-Meteo may be rate limiting (429 in logs) |
| Phone app can't connect | Run with `--host 0.0.0.0`, use the LAN IP (Android emulator: `10.0.2.2`), allow port 8000 in the firewall |
| CORS error in Expo web | Add the web origin to `CORS_ORIGINS` |
| `LOCATION_REQUIRED` from chat | The question named no place and no coordinates were sent: send device GPS |
| `ModuleNotFoundError: app` | Run commands from the `backend/` folder |

## 17. How the frontend should communicate with the backend

- Base URL from app config, e.g. `http://<LAN-IP>:8000/api/v1`. Send `Content-Type: application/json` on POST, plus `X-API-Key` if enabled.
- Always check the HTTP status; on non-2xx read `error.code` for logic and `error.message` for display.
- Send device GPS with chat requests (`latitude`, `longitude`) so "here" questions work. A place named in the message takes priority.
- Send a stable `session_id` per device/chat thread so conversations can be grouped.
- Show `advisories` with a clear "WeatherGPT advisory, not an official warning" label. Show official `alerts` separately.
- Use `units` from the response rather than hard-coding them.

```ts
const res = await fetch(`${API_BASE}/chat`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message, language: "en", latitude, longitude, session_id }),
});
const data = await res.json();
if (!res.ok) throw new Error(data.error?.message ?? "Something went wrong");
```

## Team integration notes

- **Member 1 – Mobile:** use the contract in sections 11–13 and 17. `/docs` is the live reference; the OpenAPI JSON at `/openapi.json` can generate TypeScript types.
- **Member 3 – AI:** prompts and provider code live in `app/services/ai_service.py` (Groq by default). To add a provider, subclass `AIService`, implement `_complete()`, and add it to `build_ai_service()`. The intent contract is `QueryIntent` in `app/schemas/chat.py`; keep the LLM away from producing weather values.
- **Member 4 – Weather data:** to add IMD or another source, implement `WeatherProvider` (`fetch_current`, `fetch_forecast`) returning the schemas in `app/schemas/weather.py`, then select it in `get_weather_service()` (`app/api/deps.py`). For official warnings, implement `AlertProvider` in `alert_service.py` and register it in `build_alert_provider()`. The app does not change.
- **Member 5 – Voice/Maps:** speech-to-text output goes to `POST /api/v1/chat` as `message` with `language`; `answer` is plain text ready for text-to-speech. Map pins and search use `/location/geocode` and the `location` object returned by every endpoint; weather for a tapped map point is `/weather/current?latitude=..&longitude=..`.
