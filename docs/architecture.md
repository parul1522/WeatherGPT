# Architecture

```
mobile (Expo) / API client
        │
        ▼
backend/app  (FastAPI)
  api/chat.py ──► services/ai_service.py ──► ai.agents.weather_agent.ask_weathergpt()
  api/alerts.py ─► services/alert_service.py ─► ai.tools.alert_tool (IMD)
  api/climate.py ► services/climate_service.py ► ai.tools.climate_tool
  api/weather.py ► services/weather_service.py ► backend/weather_data (Open-Meteo daily)

ai/  (project root package)
  agents/weather_agent.py   query understanding → context merge → tools
  agents/advisory_agent.py  rule-based answers from verified data
  agents/alert_agent.py     alert status → message (no LLM)
  tools/                    weather_tool, forecast_tool (hourly periods), alert_tool, climate_tool
  guardrails/               validation.py, hallucination_check.py
  language/                 detector.py, translator.py (en/hi)
  prompts/, config.py
```

Chat pipeline: user query → query understanding (Groq, rule-based fallback)
→ conversation context (per `session_id`) → intent/entity resolution → weather
/ forecast / alert / climate tool → data validation → LLM response → hallucination
check (falls back to the rule-based answer) → translation → reply.

Two Open-Meteo integrations exist on purpose: `ai/tools/forecast_tool.py`
(hourly, powers morning/afternoon/evening/night) serves chat;
`backend/weather_data` (daily summary) serves `GET /api/weather`.
