"""AI 채팅 (컨텍스트 주입 + Function Calling).

동작 흐름 (POST /api/chat)
  1) 데이터 요약 조회 (/api/data/summary 와 같은 함수 사용)
  2) 요약을 시스템 프롬프트에 삽입  ← 컨텍스트 주입
  3) GPT API 호출 (필요하면 GPT가 '도구'를 호출해 세부 데이터를 더 가져감)
  4) 질문/답변을 conversations 컬렉션에 자동 저장
"""
import json
from typing import Optional

from fastapi import HTTPException
from openai import OpenAI

from app.config import settings
from app.services import conversation_service, data_service

HISTORY_LIMIT = 10      # 이전 대화는 최근 10개 메시지만 GPT에 전달 (토큰 절약)
MAX_TOOL_ROUNDS = 3     # 도구 호출 반복 상한 (무한 루프·과금 방지)
RECORDS_LIMIT = 60      # 도구로 한 번에 넘겨 줄 최대 레코드 수

SYSTEM_PROMPT_TEMPLATE = """당신은 데이터 분석 비서입니다.

[데이터 설명]
- {description} / 단위: {unit}

[사용자 데이터 요약]
- 데이터 기간: {period}
- 총 레코드: {count}개
- 주요 지표: 합계 {total}, 평균 {average}, 최대 {max} ({max_date}), 최소 {min} ({min_date}), 최근값 {latest} ({latest_date})
- 최근 트렌드: {trend}

위 데이터를 기반으로 맞춤형 답변을 제공하세요.
- 요약에 없는 특정 날짜·월 단위 값이 필요하면 제공된 도구를 호출해 확인한 뒤 답하세요.
- 데이터에 없는 내용은 추측하지 말고 "데이터에 없다"고 말하세요.
- 투자 권유나 미래 값의 단정적 예측은 하지 마세요.
- 한국어로, 숫자는 천 단위 쉼표와 단위를 붙여 간결하게 답하세요."""


def build_system_prompt(summary: dict) -> str:
    m = summary["metrics"]
    return SYSTEM_PROMPT_TEMPLATE.format(
        description=summary["description"], unit=summary["unit"],
        period=summary["period"], count=summary["count"], trend=summary["trend"],
        total=f"{m['total']:,}", average=f"{m['average']:,}", max=f"{m['max']:,}", max_date=m["max_date"],
        min=f"{m['min']:,}", min_date=m["min_date"], latest=f"{m['latest']:,}", latest_date=m["latest_date"],
    )


# ---------- Function Calling 도구 정의 ----------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_data_summary",
            "description": "저장된 시계열 데이터의 최신 요약(기간, 개수, 평균/최대/최소, 추세)을 조회한다.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_monthly_statistics",
            "description": "월별 평균/최대/최소와 표준편차·일간 변동성을 조회한다. 월 비교, 변동성 질문에 사용.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_data_records",
            "description": "특정 기간의 일별 원본 레코드(date, value, memo)를 조회한다. 특정 날짜·짧은 기간 질문에 사용.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "시작일 YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "종료일 YYYY-MM-DD"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_recent_conversations",
            "description": "저장된 이전 대화 목록(제목, 메시지 수)을 조회한다. '전에 무슨 질문 했지?' 같은 질문에 사용.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def run_tool(name: str, args: dict) -> dict:
    if name == "get_data_summary":
        return data_service.get_summary()
    if name == "get_monthly_statistics":
        stats = data_service.get_statistics()
        stats.pop("series", None)  # 일별 시계열은 너무 길어서 제외
        return stats
    if name == "get_data_records":
        items = data_service.list_data(start=args.get("start_date"), end=args.get("end_date"))
        return {"count": len(items), "records": items[:RECORDS_LIMIT], "truncated": len(items) > RECORDS_LIMIT}
    if name == "list_recent_conversations":
        return {"conversations": conversation_service.list_conversations()[:10]}
    return {"error": f"알 수 없는 도구: {name}"}


# ---------- GPT 호출 ----------
def _client() -> OpenAI:
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
    kwargs = {"api_key": settings.OPENAI_API_KEY, "timeout": 60}
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = settings.OPENAI_BASE_URL
    return OpenAI(**kwargs)


def _token_kwargs() -> dict:
    # gpt-5 / o 시리즈는 max_tokens 대신 max_completion_tokens를 사용한다.
    model = settings.OPENAI_MODEL.lower()
    if model.startswith(("gpt-5", "o1", "o3", "o4")):
        return {"max_completion_tokens": settings.OPENAI_MAX_TOKENS}
    return {"max_tokens": settings.OPENAI_MAX_TOKENS}


def _call_gpt(client: OpenAI, messages: list[dict], use_tools: bool) -> tuple[str, list[str]]:
    tools_used: list[str] = []
    for round_no in range(MAX_TOOL_ROUNDS + 1):
        params = {"model": settings.OPENAI_MODEL, "messages": messages, **_token_kwargs()}
        # 마지막 라운드에서는 도구를 빼서 반드시 글로 된 답을 받는다.
        if use_tools and round_no < MAX_TOOL_ROUNDS:
            params["tools"] = TOOLS
        response = client.chat.completions.create(**params)
        msg = response.choices[0].message
        if not getattr(msg, "tool_calls", None):
            return (msg.content or "").strip(), tools_used

        # GPT가 도구 호출을 요청한 경우 → 실행 결과를 다시 GPT에 전달
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in msg.tool_calls
            ],
        })
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tools_used.append(call.function.name)
            result = run_tool(call.function.name, args)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, ensure_ascii=False)})
    return "답변을 만드는 중 도구 호출 한도를 넘었습니다. 질문을 조금 더 구체적으로 해 주세요.", tools_used


def chat(user_message: str, conversation_id: Optional[str] = None) -> dict:
    # 1) 데이터 요약 조회
    summary = data_service.get_summary()
    # 2) 요약을 시스템 프롬프트에 주입
    messages: list[dict] = [{"role": "system", "content": build_system_prompt(summary)}]

    if conversation_id:  # 이어지는 대화라면 이전 메시지 일부를 함께 보냄
        previous = conversation_service.get_conversation(conversation_id)["messages"]
        messages += [{"role": m["role"], "content": m["content"]} for m in previous[-HISTORY_LIMIT:]]
    messages.append({"role": "user", "content": user_message})

    # 3) GPT 호출
    client = _client()
    try:
        reply, tools_used = _call_gpt(client, list(messages), settings.USE_TOOLS)
    except HTTPException:
        raise
    except Exception as first_error:
        if not settings.USE_TOOLS:
            raise HTTPException(status_code=502, detail=f"AI 응답 실패: {first_error}") from first_error
        # 도구 호출을 지원하지 않는 서버일 수 있으므로 도구 없이 한 번 더 시도
        try:
            reply, tools_used = _call_gpt(client, list(messages), False)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"AI 응답 실패: {exc}") from exc
    if not reply:
        reply = "(빈 응답) 잠시 후 다시 질문해 주세요."

    # 4) 대화 자동 저장
    new_messages = [{"role": "user", "content": user_message}, {"role": "assistant", "content": reply}]
    if conversation_id:
        conversation_service.append_messages(conversation_id, new_messages)
    else:
        conversation_id = conversation_service.create_conversation(new_messages)["id"]

    return {"reply": reply, "conversation_id": conversation_id, "summary": summary, "tools_used": tools_used}
