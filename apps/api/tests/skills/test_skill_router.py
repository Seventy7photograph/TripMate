# 文件说明：后端自动化测试：Skill Router。
from datetime import date

from app.core.config import Settings
from app.schemas.ai import TripBriefContract
from app.skills.registry import load_configured_registry
from app.skills.router import SkillRouter


def manifests():
    return load_configured_registry(
        Settings(app_env="test")
    ).latest_manifests()


def test_router_asks_before_guessing() -> None:
    decision = SkillRouter().route(
        text="想去个安静的地方",
        available_skills=manifests(),
    )

    assert decision.confidence < 0.7
    assert decision.needs_clarification is True
    assert decision.selected_skills == []
    assert decision.needed_clarifications


def test_router_drops_unknown_skill() -> None:
    decision = SkillRouter().route(
        text="泉州三天看古城",
        available_skills=manifests(),
    )

    assert "shell-execution" not in decision.selected_skills
    assert decision.selected_skills == []


def test_router_selects_only_available_planning_skills() -> None:
    brief = TripBriefContract(
        destination="泉州",
        origin="上海",
        start_date=date(2026, 12, 20),
        end_date=date(2026, 12, 22),
        party_size=2,
        budget_minor=300_000,
        interests=["古建", "美食"],
        lodging_preferences=["地铁"],
    )

    decision = SkillRouter().route(
        text="泉州三天看古城，想吃小吃，住宿靠近地铁。",
        brief=brief,
        available_skills=manifests(),
    )

    assert decision.confidence >= 0.7
    assert decision.needs_clarification is False
    assert "destination-research" in decision.selected_skills
    assert "food-planning" in decision.selected_skills
    assert "lodging-area-selection" in decision.selected_skills
    assert "shell-execution" not in decision.selected_skills
    assert decision.budget.max_tool_calls > 0
