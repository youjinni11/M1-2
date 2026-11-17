"""환경 변수 설정 모음.

API 키·서비스 계정 키 같은 비밀값은 코드에 직접 쓰지 않고
환경 변수(.env 파일 또는 Render 대시보드)에서 읽어 온다.
"""
import os

from dotenv import load_dotenv

# 로컬 개발 시 backend/.env 파일을 읽는다. (배포 환경에서는 대시보드 환경 변수 사용)
load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    # OpenAI (GPT)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    # 코디세이 제공 OpenAI 호환 서버 등을 쓸 때만 설정 (비우면 OpenAI 공식 서버)
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # 과금 방지를 위한 응답 토큰 상한
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "800"))
    # GPT가 내부 기능을 도구로 호출(Function Calling)하도록 할지 여부
    USE_TOOLS: bool = os.getenv("USE_TOOLS", "true").lower() == "true"

    # Firebase 서비스 계정 키: JSON 문자열 또는 파일 경로 중 하나
    FIREBASE_SERVICE_ACCOUNT_JSON: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    FIREBASE_SERVICE_ACCOUNT_PATH: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "")

    # CORS 허용 도메인 목록 (쉼표로 구분)
    ALLOWED_ORIGINS: list[str] = _split_csv(
        os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000",
        )
    )

    # 초기 데이터 적재(seed) API 보호용 토큰. 비우면 seed API 비활성화
    ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "")

    # 데이터 설명 (AI 시스템 프롬프트에 함께 들어감)
    DATA_DESCRIPTION: str = os.getenv(
        "DATA_DESCRIPTION",
        "원/달러 환율(1달러당 원화, 일별 종가 기준, 출처: FRED DEXKOUS)",
    )
    DATA_UNIT: str = os.getenv("DATA_UNIT", "원")


settings = Settings()
