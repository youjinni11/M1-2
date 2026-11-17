"""Pydantic 모델: 요청 데이터 검증 + 응답 형식 정의.

잘못된 값(날짜 형식 오류, 숫자가 아닌 value, 빈 메시지 등)이 들어오면
FastAPI가 자동으로 422 에러를 돌려주므로, DB에 잘못된 데이터가 들어가지 않는다.
"""
from datetime import date as Date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------- 시계열 데이터 ----------
class DataCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"date": "2026-01-02", "value": 1450.25, "memo": "새해 첫 거래일"}}
    )

    date: Date = Field(..., description="날짜 (YYYY-MM-DD)")
    value: float = Field(..., gt=0, lt=1_000_000_000, allow_inf_nan=False, description="값 (0보다 커야 함)")
    memo: str = Field("", max_length=200, description="메모 (최대 200자)")

    @field_validator("memo")
    @classmethod
    def strip_memo(cls, v: str) -> str:
        return v.strip()


class DataUpdate(BaseModel):
    """수정할 필드만 보내면 된다. (최소 1개)"""

    model_config = ConfigDict(json_schema_extra={"example": {"value": 1455.0, "memo": "수정됨"}})

    date: Optional[Date] = None
    value: Optional[float] = Field(None, gt=0, lt=1_000_000_000, allow_inf_nan=False)
    memo: Optional[str] = Field(None, max_length=200)

    @model_validator(mode="after")
    def at_least_one(self):
        if self.date is None and self.value is None and self.memo is None:
            raise ValueError("date, value, memo 중 최소 1개는 보내야 합니다.")
        return self


class DataItem(BaseModel):
    id: str
    date: str
    value: float
    memo: str = ""


class DataListResponse(BaseModel):
    count: int
    items: list[DataItem]


class Metrics(BaseModel):
    total: float
    average: float
    max: float
    max_date: str
    min: float
    min_date: str
    latest: float
    latest_date: str


class SummaryResponse(BaseModel):
    period: str
    count: int
    metrics: Metrics
    trend: str
    description: str
    unit: str


class StatisticsResponse(BaseModel):
    """보너스: 요약보다 자세한 통계 + 그래프용 시계열"""

    std_dev: float
    daily_change_avg_pct: float
    volatility_pct: float
    monthly: list[dict]
    moving_average_window: int
    series: list[dict]


# ---------- 대화 ----------
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)


class ConversationCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "환율 질문",
                "messages": [
                    {"role": "user", "content": "올해 평균 환율은?"},
                    {"role": "assistant", "content": "약 1,421원입니다."},
                ],
            }
        }
    )

    title: Optional[str] = Field(None, max_length=100)
    messages: list[Message] = Field(..., min_length=1, max_length=200)


class ConversationSummary(BaseModel):
    """목록 조회용 (messages 미포함 → 응답을 가볍게)"""

    id: str
    title: str
    message_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConversationDetail(ConversationSummary):
    """단건 조회용 (messages 포함)"""

    messages: list[Message]


# ---------- 채팅 ----------
class ChatRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"message": "최근 환율 추세가 어때?", "conversation_id": None}}
    )

    message: str = Field(..., min_length=1, max_length=1000, description="사용자 질문")
    conversation_id: Optional[str] = Field(None, description="이어서 대화할 경우 기존 대화 ID")

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("메시지가 비어 있습니다.")
        return v.strip()


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    summary: SummaryResponse
    tools_used: list[str] = []
