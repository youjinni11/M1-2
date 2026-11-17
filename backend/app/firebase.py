"""Firebase(Firestore) 연결.

서비스 계정 키는 환경 변수로만 받는다.
- FIREBASE_SERVICE_ACCOUNT_JSON : 키 파일 내용(JSON 문자열) 전체  ← Render 배포용
- FIREBASE_SERVICE_ACCOUNT_PATH : 키 파일 경로                     ← 로컬 개발용
"""
import json

import firebase_admin
from fastapi import HTTPException
from firebase_admin import credentials, firestore

from app.config import settings

# 컬렉션 이름
DATA_COLLECTION = "data"
CONVERSATION_COLLECTION = "conversations"

_db = None


def _load_credentials() -> credentials.Certificate:
    if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
        info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
        return credentials.Certificate(info)
    if settings.FIREBASE_SERVICE_ACCOUNT_PATH:
        return credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    raise RuntimeError(
        "Firebase 서비스 계정 키가 없습니다. "
        "FIREBASE_SERVICE_ACCOUNT_JSON 또는 FIREBASE_SERVICE_ACCOUNT_PATH 환경 변수를 설정하세요."
    )


def get_db():
    """Firestore 클라이언트를 돌려준다. 처음 호출될 때 한 번만 초기화한다."""
    global _db
    if _db is None:
        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app(_load_credentials())
            _db = firestore.client()
        except Exception as exc:  # 키 누락/형식 오류
            raise HTTPException(status_code=503, detail=f"DB 연결 실패: {exc}") from exc
    return _db
