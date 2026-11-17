"""data 컬렉션 CRUD (Firestore와 직접 통신하는 부분)."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from google.cloud.firestore_v1.base_query import FieldFilter

from app.config import settings
from app.firebase import DATA_COLLECTION, get_db
from app.services.analysis import compute_statistics, compute_summary


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_item(doc) -> dict:
    d = doc.to_dict() or {}
    return {"id": doc.id, "date": d.get("date", ""), "value": d.get("value", 0), "memo": d.get("memo", "")}


def _ensure_unique_date(date_str: str, exclude_id: Optional[str] = None) -> None:
    """같은 날짜 데이터가 이미 있으면 409 에러 (시계열이므로 날짜당 1개)"""
    docs = get_db().collection(DATA_COLLECTION).where(filter=FieldFilter("date", "==", date_str)).limit(2).stream()
    for doc in docs:
        if doc.id != exclude_id:
            raise HTTPException(status_code=409, detail=f"{date_str} 날짜의 데이터가 이미 있습니다. (id: {doc.id})")


def list_data(start: Optional[str] = None, end: Optional[str] = None, limit: Optional[int] = None) -> list[dict]:
    """날짜 오름차순 목록. start/end(YYYY-MM-DD)로 기간을 거른다."""
    query = get_db().collection(DATA_COLLECTION).order_by("date")
    items = [_to_item(doc) for doc in query.stream()]
    if start:
        items = [i for i in items if i["date"] >= start]
    if end:
        items = [i for i in items if i["date"] <= end]
    if limit:
        items = items[-limit:]  # 최근 limit개
    return items


def create_data(date_str: str, value: float, memo: str) -> dict:
    _ensure_unique_date(date_str)
    ref = get_db().collection(DATA_COLLECTION).document()
    ref.set({"date": date_str, "value": value, "memo": memo, "created_at": _now(), "updated_at": _now()})
    return {"id": ref.id, "date": date_str, "value": value, "memo": memo}


def update_data(doc_id: str, changes: dict) -> dict:
    ref = get_db().collection(DATA_COLLECTION).document(doc_id)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="해당 ID의 데이터가 없습니다.")
    if "date" in changes:
        _ensure_unique_date(changes["date"], exclude_id=doc_id)
    changes["updated_at"] = _now()
    ref.update(changes)
    return _to_item(ref.get())


def delete_data(doc_id: str) -> None:
    ref = get_db().collection(DATA_COLLECTION).document(doc_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="해당 ID의 데이터가 없습니다.")
    ref.delete()


def get_summary() -> dict:
    return compute_summary(list_data(), settings.DATA_DESCRIPTION, settings.DATA_UNIT)


def get_statistics() -> dict:
    return compute_statistics(list_data())


def bulk_insert(rows: list[dict], reset: bool = False) -> int:
    """초기 데이터 적재용. reset=True면 기존 data 컬렉션을 비우고 넣는다."""
    db = get_db()
    col = db.collection(DATA_COLLECTION)
    if reset:
        for doc in col.stream():
            doc.reference.delete()
    existing = {doc.to_dict().get("date") for doc in col.stream()}
    batch, written = db.batch(), 0
    for row in rows:
        if row["date"] in existing:
            continue
        batch.set(col.document(), {**row, "created_at": _now(), "updated_at": _now()})
        written += 1
        if written % 400 == 0:  # Firestore 배치 한도(500) 이하로 끊어서 커밋
            batch.commit()
            batch = db.batch()
    batch.commit()
    return written
