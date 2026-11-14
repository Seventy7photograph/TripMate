# 文件说明：后端自动化测试：test_production_manifests。
from pathlib import Path

import pytest

from app.skills.registry import SkillRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = PROJECT_ROOT / "skills"


@pytest.mark.parametrize(
    "skill_name",
    [
        "destination-research",
        "route-optimization",
        "budget-optimization",
        "evidence-verification",
        "trip-intent-routing",
        "travel-memory",
        "social-copywriting",
        "weather-and-clothing",
        "food-planning",
        "lodging-area-selection",
        "safety-briefing",
        "attachment-understanding",
    ],
)
def test_first_wave_skill_is_active_and_bounded(skill_name: str) -> None:
    registry = SkillRegistry(
        known_tools={
            "search_places",
            "get_route",
            "calculate_budget",
            "get_authorized_memory_context",
            "get_weather",
            "search_nearby_places",
            "get_place_detail",
            "get_place_facts",
            "get_route_matrix",
            "get_altitude",
            "extract_attachment",
            "calculate_budget",
            "get_authorized_memory_context",
        }
    )
    registry.load(SKILLS_ROOT)

    skill = registry.get(skill_name)

    assert skill.status == "active"
    assert skill.max_tool_calls <= 8
    assert set(skill.allowed_tools) <= registry.known_tools
    assert (SKILLS_ROOT / skill_name / "SKILL.md").exists()


def test_evidence_verification_has_no_external_tools() -> None:
    registry = SkillRegistry(
        known_tools={
            "search_places",
            "get_route",
            "calculate_budget",
            "get_authorized_memory_context",
            "get_weather",
            "search_nearby_places",
            "get_place_detail",
            "get_place_facts",
            "get_route_matrix",
            "get_altitude",
            "extract_attachment",
        }
    )
    registry.load(SKILLS_ROOT)

    assert registry.get("evidence-verification").allowed_tools == []


def test_contract_skill_capabilities_are_explicit() -> None:
    registry = SkillRegistry(
        known_tools={
            "search_places",
            "get_route",
            "calculate_budget",
            "get_authorized_memory_context",
            "get_weather",
            "search_nearby_places",
            "get_place_detail",
            "get_place_facts",
            "get_route_matrix",
            "get_altitude",
            "extract_attachment",
        }
    )
    registry.load(SKILLS_ROOT)

    assert registry.get("trip-intent-routing").allowed_tools == []
    assert registry.get("travel-memory").allowed_tools == [
        "get_authorized_memory_context"
    ]
    assert registry.get("social-copywriting").allowed_tools == []


def test_task6_skills_require_evidence() -> None:
    registry = SkillRegistry(
        known_tools={
            "get_weather",
            "search_places",
            "get_place_facts",
            "get_route_matrix",
            "get_altitude",
            "get_route",
            "calculate_budget",
            "get_authorized_memory_context",
            "extract_attachment",
        }
    )
    registry.load(SKILLS_ROOT)

    for name in (
        "weather-and-clothing",
        "food-planning",
        "lodging-area-selection",
        "safety-briefing",
        "attachment-understanding",
    ):
        assert registry.get(name).requires_evidence is True
