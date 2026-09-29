# WeatherGPT

AI-powered multilingual weather assistant — chat, forecasts, alerts, voice, maps and agri-advisories.

## Team ownership
| Folder | Owner | Scope |
|---|---|---|
| `mobile/` | Member 1 | Expo / React Native app |
| `backend/` | Member 2 | FastAPI API, DB, services |
| `ai/` | Member 3 | Prompts, agents, tools, guardrails |
| `backend/weather_data/` | Member 4 | Providers, processing, alerts, cache (Python package; was `weather-data/`) |
| `advanced/` | Member 5 | Voice, maps, multilingual, agriculture |

## Quick start
See [docs/setup.md](docs/setup.md).

## Run from the project root
`pip install -r requirements.txt`, copy `.env.example` to `.env`, then
`uvicorn backend.app.main:app --reload`. Tests: `pytest`.
