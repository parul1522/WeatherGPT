from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    lang: str = "en"
    lat: float | None = None
    lon: float | None = None
    # Optional conversation id. Send back the ``session_id`` returned by the
    # previous reply to get follow-up handling ("What about evening?").
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    lang: str = "en"
    session_id: str | None = None
