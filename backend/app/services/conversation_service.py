"""conversations 컬렉션 저장/조회/삭제."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

from app.firebase import CONVERSATION_COLLECTION, get_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_title(messages: list[dict]) -> str:
    first_user = next((m["content"] for m in messages if m["role"] == "user"), "새 대화")
    return first_user[:30] + ("…" if len(first_user) > 30 else "")


def _to_summary(doc) -> dict:
    d = doc.to_dict() or {}
    return {
        "id": doc.id,
        "title": d.get("title", ""),
        "message_count": len(d.get("messages", [])),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }


def create_conversation(messages: list[dict], title: Optional[str] = None) -> dict:
    ref = get_db().collection(CONVERSATION_COLLECTION).document()
    data = {
        "title": title or _make_title(messages),
        "messages": messages,
        "created_at": _now(),
        "updated_at": _now(),
    }
    ref.set(data)
    return {"id": ref.id, **data, "message_count": len(messages)}


def append_messages(conversation_id: str, messages: list[dict]) -> None:
    ref = get_db().collection(CONVERSATION_COLLECTION).document(conversation_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="해당 ID의 대화가 없습니다.")
    # Firestore ArrayUnion은 똑같은 메시지(같은 질문 반복)를 하나로 합쳐 버리므로,
    # 기존 목록을 읽어 뒤에 그대로 이어 붙인다.
    current = (ref.get().to_dict() or {}).get("messages", [])
    ref.update({"messages": current + messages, "updated_at": _now()})


def list_conversations() -> list[dict]:
    """대화 목록 (최근 수정순, messages 미포함)"""
    docs = get_db().collection(CONVERSATION_COLLECTION).stream()
    items = [_to_summary(doc) for doc in docs]
    return sorted(items, key=lambda c: c.get("updated_at") or "", reverse=True)


def get_conversation(conversation_id: str) -> dict:
    snap = get_db().collection(CONVERSATION_COLLECTION).document(conversation_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="해당 ID의 대화가 없습니다.")
    return {**_to_summary(snap), "messages": (snap.to_dict() or {}).get("messages", [])}


def delete_conversation(conversation_id: str) -> None:
    ref = get_db().collection(CONVERSATION_COLLECTION).document(conversation_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="해당 ID의 대화가 없습니다.")
    ref.delete()
