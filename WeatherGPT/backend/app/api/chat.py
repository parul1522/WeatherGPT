from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # TODO: call ai_service
    return ChatResponse(reply=f"Echo: {req.message}", lang=req.lang)
