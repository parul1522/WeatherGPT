from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):

    message = req.message.lower()

    if "weather" in message:
        reply = "I can provide weather information for your selected location."

    elif "alert" in message:
        reply = "I can check weather alerts for your selected location."

    elif "climate" in message:
        reply = "I can provide climate information for your selected location."

    else:
        reply = f"You asked: {req.message}"

    return ChatResponse(
        reply=reply,
        lang=req.lang
    )