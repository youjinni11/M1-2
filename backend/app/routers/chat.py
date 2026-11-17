"""AI 챗봇 API (컨텍스트 주입)."""
from fastapi import APIRouter

from app.schemas import ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, summary="AI 대화 (데이터 요약 주입 → GPT → 자동 저장)")
def chat(payload: ChatRequest):
    return chat_service.chat(payload.message, payload.conversation_id)
