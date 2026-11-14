# 文件说明：后端自动化测试：safety-briefing Skill。
from datetime import date

from app.skills.production import SafetyBriefingInput
from tests.skills.task6_runtime import skill_context, task6_runtime


async def test_safety_skill_triggers_above_2500m() -> None:
    skills, tools, context, executor, _ = task6_runtime()
    manifest = skills.get("safety-briefing")

    result = await executor.execute(
        manifest,
        skill_context(tools, context, manifest.name),
        SafetyBriefingInput(
            altitude_m=3200,
            dates=[date(2026, 12, 20)],
            party=["adult"],
        ),
    )

    assert result.output.level in {"warning", "high"}
    assert any("高海拔" in item for item in result.output.reminders)
    assert "不替代医疗意见" in result.output.disclaimer
    assert result.output.evidence_ids
