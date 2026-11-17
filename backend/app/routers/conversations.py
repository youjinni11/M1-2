"""대화 기록 API.

'대화 불러오기'는 (A) 방식: GET /api/conversations/{id} 로 전체 messages 조회.
목록(GET /api/conversations)에는 messages를 넣지 않고 message_count만 준다. (응답을 가볍게)
"""
from fastapi import APIRouter, Response, status

from app.schemas import ConversationCreate, ConversationDetail, ConversationSummary
from app.services import conversation_service

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED, summary="대화 저장")
def create_conversation(payload: ConversationCreate):
    messages = [m.model_dump() for m in payload.messages]
    return conversation_service.create_conversation(messages, payload.title)


@router.get("", response_model=list[ConversationSummary], summary="대화 목록 조회 (messages 미포함)")
def list_conversations():
    return conversation_service.list_conversations()


@router.get("/{id}", response_model=ConversationDetail, summary="특정 대화 불러오기 (messages 포함)")
def get_conversation(id: str):
    return conversation_service.get_conversation(id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="대화 삭제")
def delete_conversation(id: str):
    conversation_service.delete_conversation(id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
