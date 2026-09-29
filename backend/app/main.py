from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import chat, weather, alerts, climate, location

app = FastAPI(title="WeatherGPT API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(weather.router, prefix="/api/weather", tags=["weather"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(climate.router, prefix="/api/climate", tags=["climate"])
app.include_router(location.router, prefix="/api/location", tags=["location"])


@app.get("/health")
def health():
    return {"status": "ok"}
