# 文件说明：后端自动化测试：富行程契约。
from datetime import date

from app.schemas.ai import DayPlanContract


def test_day_plan_contract_carries_rich_travel_sections() -> None:
    day = DayPlanContract(
        id="day-1",
        date=date(2026, 12, 20),
        theme="古城",
        stops=[],
        weather={
            "status": "known",
            "summary": "晴，22/11°C",
            "clothing_advice": ["早晚加外套"],
            "risk": "low",
            "evidence_ids": ["ev-weather"],
        },
        meals=[
            {
                "meal": "lunch",
                "status": "known",
                "place_name": "西街小吃",
                "timing": "12:00",
                "opening_hours_status": "known",
                "evidence_ids": ["ev-food"],
            }
        ],
        transport=[],
        lodging_area={
            "status": "known",
            "area": "钟楼地铁站周边",
            "reason": "交通方便",
            "evidence_ids": ["ev-lodging"],
        },
        safety={
            "level": "low",
            "reminders": ["保管随身物品"],
            "disclaimer": "不替代医疗意见",
            "evidence_ids": ["ev-safety"],
        },
        daily_summary="上午古城，下午休息。",
        alternatives=["雨天改为博物馆"],
        evidence_ids=[
            "ev-weather",
            "ev-food",
            "ev-lodging",
            "ev-safety",
        ],
    )

    assert day.weather.status == "known"
    assert day.meals[0].place_name == "西街小吃"
    assert day.lodging_area.area == "钟楼地铁站周边"
    assert day.safety.disclaimer == "不替代医疗意见"
