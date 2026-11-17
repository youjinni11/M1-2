"""데이터 API: CRUD 4개 + summary 1개 (+ 보너스 statistics/export, 관리자 seed)."""
import csv
import io
import json
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Response, status

from app.config import settings
from app.schemas import (DataCreate, DataItem, DataListResponse, DataUpdate,
                         StatisticsResponse, SummaryResponse)
from app.services import data_service

router = APIRouter(prefix="/api/data", tags=["data"])

SEED_CSV = Path(__file__).resolve().parents[2] / "data" / "usdkrw_2025.csv"
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


# ※ /summary 등 고정 경로를 /{id} 보다 먼저 선언해야 경로가 섞이지 않는다.
@router.get("/summary", response_model=SummaryResponse, summary="데이터 요약 (프롬프트 주입용)")
def get_summary():
    return data_service.get_summary()


@router.get("/statistics", response_model=StatisticsResponse, summary="[보너스] 상세 통계 + 그래프용 시계열")
def get_statistics():
    return data_service.get_statistics()


@router.get("/export", summary="[보너스] 데이터 내보내기 (CSV/JSON 다운로드)")
def export_data(format: Literal["csv", "json"] = "csv"):
    items = data_service.list_data()
    if format == "json":
        body = json.dumps(items, ensure_ascii=False, indent=2)
        return Response(body, media_type="application/json",
                        headers={"Content-Disposition": "attachment; filename=data.json"})
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["id", "date", "value", "memo"])
    writer.writeheader()
    writer.writerows(items)
    # 엑셀에서 한글이 깨지지 않도록 BOM 추가
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=data.csv"})


@router.post("", response_model=DataItem, status_code=status.HTTP_201_CREATED, summary="새 데이터 추가")
def create_data(payload: DataCreate):
    return data_service.create_data(payload.date.isoformat(), payload.value, payload.memo)


@router.get("", response_model=DataListResponse, summary="데이터 목록 조회 (날짜 오름차순)")
def list_data(
    start: Optional[str] = Query(None, pattern=DATE_PATTERN, description="시작일 YYYY-MM-DD"),
    end: Optional[str] = Query(None, pattern=DATE_PATTERN, description="종료일 YYYY-MM-DD"),
    limit: Optional[int] = Query(None, ge=1, le=5000, description="최근 N개만"),
):
    items = data_service.list_data(start, end, limit)
    return {"count": len(items), "items": items}


@router.put("/{id}", response_model=DataItem, summary="데이터 수정")
def update_data(id: str, payload: DataUpdate):
    changes = payload.model_dump(exclude_none=True)
    if "date" in changes:
        changes["date"] = changes["date"].isoformat()
    if "memo" in changes:
        changes["memo"] = changes["memo"].strip()
    return data_service.update_data(id, changes)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="데이터 삭제")
def delete_data(id: str):
    data_service.delete_data(id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/seed", summary="[관리자] 초기 데이터(2025 원/달러 환율 250개) 적재", include_in_schema=True)
def seed_data(reset: bool = False, x_admin_token: Optional[str] = Header(None)):
    if not settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="ADMIN_TOKEN이 설정되지 않아 seed 기능이 꺼져 있습니다.")
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="관리자 토큰이 올바르지 않습니다.")
    with SEED_CSV.open(encoding="utf-8") as f:
        rows = [{"date": r["date"], "value": float(r["value"]), "memo": r.get("memo", "")} for r in csv.DictReader(f)]
    written = data_service.bulk_insert(rows, reset=reset)
    return {"source_rows": len(rows), "inserted": written}
