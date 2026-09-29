from fastapi import APIRouter, HTTPException

from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.services import ai_service

router = APIRouter()


# Plain ``def``: the AI pipeline is blocking, so FastAPI runs it in a thread.
@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        result = ai_service.answer_chat(req.message, req.session_id)
    except ai_service.AIServiceError as error:
        raise HTTPException(status_code=503, detail=str(error))

    return ChatResponse(**result)
