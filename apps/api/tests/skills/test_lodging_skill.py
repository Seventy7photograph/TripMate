# 文件说明：后端自动化测试：lodging-area-selection Skill。
from app.skills.production import LodgingAreaSelectionInput
from tests.skills.task6_runtime import skill_context, task6_runtime


async def test_lodging_skill_returns_areas_without_room_inventory() -> None:
    skills, tools, context, executor, _ = task6_runtime()
    manifest = skills.get("lodging-area-selection")

    result = await executor.execute(
        manifest,
        skill_context(tools, context, manifest.name),
        LodgingAreaSelectionInput(
            city="泉州",
            preferences=["地铁", "安静"],
            limit=2,
        ),
    )

    assert result.output.areas
    assert "有房" not in result.output.availability_notice
    assert "库存" not in result.output.availability_notice
    assert result.output.evidence_ids
