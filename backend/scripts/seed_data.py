"""초기 데이터 적재 스크립트 (로컬 실행용).

사용법 (backend 폴더에서):
    python -m scripts.seed_data            # 없는 날짜만 추가
    python -m scripts.seed_data --reset    # data 컬렉션을 비우고 다시 적재

배포 서버에서는 Swagger의 POST /api/data/seed (X-Admin-Token 헤더 필요)로도 같은 작업을 할 수 있다.
"""
import argparse
import csv
from pathlib import Path

from app.services.data_service import bulk_insert

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "usdkrw_2025.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="기존 data 컬렉션을 비우고 적재")
    args = parser.parse_args()

    with CSV_PATH.open(encoding="utf-8") as f:
        rows = [{"date": r["date"], "value": float(r["value"]), "memo": r.get("memo", "")} for r in csv.DictReader(f)]
    written = bulk_insert(rows, reset=args.reset)
    print(f"CSV {len(rows)}행 중 {written}행을 Firestore 'data' 컬렉션에 저장했습니다.")


if __name__ == "__main__":
    main()
