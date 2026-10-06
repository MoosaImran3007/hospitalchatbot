from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from models.chat import ChatRequest
from services.dify_services import stream_chat
from auth.dependencies import get_current_user


router = APIRouter()


@router.post("/chat")
def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):

    return StreamingResponse(
        stream_chat(
            request,
            current_user
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )