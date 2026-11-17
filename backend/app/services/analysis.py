"""시계열 분석 로직 (DB와 무관한 순수 계산 함수).

DB에서 꺼낸 데이터 목록을 받아 '요약 정보'와 '상세 통계'를 만든다.
이 요약이 AI 시스템 프롬프트에 주입된다.
"""
import statistics
from collections import OrderedDict

TREND_WINDOW = 20        # 추세 비교 구간 (최근 20개 vs 직전 20개)
TREND_THRESHOLD = 0.5    # ±0.5% 이내면 '유지'
MA_WINDOW = 20           # 그래프용 이동평균 구간


def _r(x: float, n: int = 2) -> float:
    return round(float(x), n)


def compute_trend(values: list[float]) -> str:
    """최근 N개 평균과 직전 N개 평균을 비교해 증가/감소/유지를 판단한다."""
    if len(values) < 2:
        return "데이터 부족"
    window = min(TREND_WINDOW, len(values) // 2)
    recent = statistics.mean(values[-window:])
    previous = statistics.mean(values[-2 * window:-window])
    change = (recent - previous) / previous * 100
    if change > TREND_THRESHOLD:
        label = "상승"
    elif change < -TREND_THRESHOLD:
        label = "하락"
    else:
        label = "유지"
    return f"{label} (최근 {window}개 평균이 직전 {window}개 평균 대비 {change:+.2f}%)"


def compute_summary(items: list[dict], description: str, unit: str) -> dict:
    """items: date 오름차순으로 정렬된 [{'date','value',...}] 목록"""
    if not items:
        return {
            "period": "데이터 없음",
            "count": 0,
            "metrics": {
                "total": 0, "average": 0, "max": 0, "max_date": "-", "min": 0,
                "min_date": "-", "latest": 0, "latest_date": "-",
            },
            "trend": "데이터 없음",
            "description": description,
            "unit": unit,
        }

    values = [float(i["value"]) for i in items]
    max_item = max(items, key=lambda i: i["value"])
    min_item = min(items, key=lambda i: i["value"])
    return {
        "period": f"{items[0]['date']} ~ {items[-1]['date']}",
        "count": len(items),
        "metrics": {
            "total": _r(sum(values)),
            "average": _r(statistics.mean(values)),
            "max": _r(max_item["value"]),
            "max_date": max_item["date"],
            "min": _r(min_item["value"]),
            "min_date": min_item["date"],
            "latest": _r(items[-1]["value"]),
            "latest_date": items[-1]["date"],
        },
        "trend": compute_trend(values),
        "description": description,
        "unit": unit,
    }


def compute_statistics(items: list[dict]) -> dict:
    """보너스: 표준편차, 일간 변동률, 월별 평균, 이동평균 시계열"""
    values = [float(i["value"]) for i in items]
    if len(values) < 2:
        return {
            "std_dev": 0, "daily_change_avg_pct": 0, "volatility_pct": 0, "monthly": [],
            "moving_average_window": MA_WINDOW,
            "series": [{"date": i["date"], "value": i["value"], "ma": None} for i in items],
        }

    changes = [(values[k] - values[k - 1]) / values[k - 1] * 100 for k in range(1, len(values))]

    monthly: "OrderedDict[str, list[float]]" = OrderedDict()
    for i in items:
        monthly.setdefault(i["date"][:7], []).append(float(i["value"]))

    series = []
    for k, i in enumerate(items):
        ma = _r(statistics.mean(values[k - MA_WINDOW + 1:k + 1])) if k + 1 >= MA_WINDOW else None
        series.append({"date": i["date"], "value": _r(i["value"]), "ma": ma})

    return {
        "std_dev": _r(statistics.stdev(values)),
        "daily_change_avg_pct": _r(statistics.mean(changes), 4),
        "volatility_pct": _r(statistics.stdev(changes), 4) if len(changes) > 1 else 0,
        "monthly": [
            {"month": m, "average": _r(statistics.mean(v)), "max": _r(max(v)), "min": _r(min(v)), "count": len(v)}
            for m, v in monthly.items()
        ],
        "moving_average_window": MA_WINDOW,
        "series": series,
    }
