# Setup

## Docker (backend + db + redis)

```bash
cp .env.example .env            # then set GROQ_API_KEY (optional, see below)
docker compose up --build       # build context is the project root
cd mobile && npm install && npx expo start
```

## Local (no Docker) — run everything from the project root

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --reload        # http://localhost:8000/docs
```

## Tests (offline — external APIs are mocked)

```bash
pytest                                        # or: python -m unittest discover -s tests -t . -v
```

`tests/test_backend_api.py` needs fastapi + httpx (installed by
requirements.txt) and is skipped otherwise.

## Chat from the command line

```bash
python -m ai.agents.weather_agent
```

## Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Groq key. Empty = run without the LLM (rule-based query understanding and rule-based answers from verified data). |
| `GROQ_MODEL` | Groq model id (default `openai/gpt-oss-20b`). |
| `IMD_DISTRICT_IDS` | Optional JSON `{"Bhopal": <verified IMD obj_id>}`. Cities without an ID answer "Weather alert data is not configured for this location." Never put guessed IDs here. |
| `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` | Backend infrastructure. |
| `EXPO_PUBLIC_API_URL` | Mobile app -> backend URL. |

`LLM_API_KEY` from earlier scaffolding has been replaced by `GROQ_API_KEY`.
