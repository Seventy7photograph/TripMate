# 文件说明：后端自动化测试：food-planning Skill。
from app.skills.production import FoodPlanningInput
from tests.skills.task6_runtime import skill_context, task6_runtime


async def test_food_skill_marks_missing_hours_unknown() -> None:
    skills, tools, context, executor, _ = task6_runtime()
    manifest = skills.get("food-planning")

    result = await executor.execute(
        manifest,
        skill_context(tools, context, manifest.name),
        FoodPlanningInput(
            meal="lunch",
            city="泉州",
            dietary=[],
            limit=2,
        ),
    )

    assert result.output.meals
    assert all(
        item.opening_hours_status in {"known", "unknown"}
        for item in result.output.meals
    )
    assert "12:00" not in result.output.evidence_free_text
    assert result.output.evidence_ids
