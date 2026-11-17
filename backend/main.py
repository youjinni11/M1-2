"""FastAPI 앱 진입점.

실행: uvicorn main:app --reload
문서: http://127.0.0.1:8000/docs (Swagger UI)
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.api_core import exceptions as gexc

from app.config import settings
from app.routers import chat, conversations, data

app = FastAPI(
    title="내 데이터를 아는 AI 비서 API",
    description="원/달러 환율 시계열 데이터를 분석·저장하고, 데이터 요약을 GPT 시스템 프롬프트에 주입해 답하는 API",
    version="1.0.0",
)

# CORS: 프론트엔드(Vercel) 도메인에서 오는 요청만 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(gexc.GoogleAPICallError)
async def firestore_error_handler(request: Request, exc: gexc.GoogleAPICallError):
    """Firestore 오류(권한·연결 등)를 500 대신 원인이 담긴 503 JSON으로 돌려준다."""
    return JSONResponse(status_code=503, content={"detail": f"DB 오류: {exc.message or exc}"})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    """예상하지 못한 오류도 JSON 형식으로 응답 (서버 내부 정보는 노출하지 않음)."""
    return JSONResponse(status_code=500, content={"detail": f"서버 오류: {type(exc).__name__}"})


app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)


@app.get("/", tags=["health"], summary="서버 상태 확인 (콜드스타트 깨우기용)")
def health():
    return {"status": "ok", "docs": "/docs"}
