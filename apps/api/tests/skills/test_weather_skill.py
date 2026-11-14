# 文件说明：后端自动化测试：weather-and-clothing Skill。
from datetime import date

from app.skills.production import WeatherClothingInput
from tests.skills.task6_runtime import skill_context, task6_runtime


async def test_weather_skill_returns_advice_with_evidence() -> None:
    skills, tools, context, executor, _ = task6_runtime()
    manifest = skills.get("weather-and-clothing")

    result = await executor.execute(
        manifest,
        skill_context(tools, context, manifest.name),
        WeatherClothingInput(city="泉州", date=date(2026, 12, 20)),
    )

    assert result.output.temperature_max_c == 22
    assert result.output.clothing_advice
    assert result.output.evidence_ids
    assert result.tool_calls == 1
