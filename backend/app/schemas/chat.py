from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    lang: str = "en"
    lat: float | None = None
    lon: float | None = None


class ChatResponse(BaseModel):
    reply: str
    lang: str = "en"
