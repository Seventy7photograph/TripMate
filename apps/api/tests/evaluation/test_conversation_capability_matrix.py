# 文件说明：后端自动化测试：旅行对话能力矩阵覆盖与契约。
from pathlib import Path

import yaml

MATRIX = Path(__file__).with_name("conversation_capability_matrix.yaml")
REQUIRED = {
    "destination",
    "food",
    "attractions",
    "planning",
    "route",
    "transport",
    "lodging",
    "weather",
    "budget",
    "policy",
    "safety",
    "live_fact",
    "follow_up",
    "greeting",
    "out_of_scope",
}


def load_matrix() -> dict[str, object]:
    payload = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_conversation_matrix_covers_every_travel_capability() -> None:
    payload = load_matrix()
    cases = payload["cases"]
    assert payload["version"] == 1
    assert {case["category"] for case in cases} == REQUIRED
    for category in REQUIRED:
        assert any(case["category"] == category and case["message"].strip() for case in cases)


def test_every_conversation_case_declares_its_routing_contract() -> None:
    cases = load_matrix()["cases"]
    for case in cases:
        assert case["intent"]
        assert isinstance(case["in_scope"], bool)
        assert isinstance(case["required_skills"], list)
        assert all(isinstance(skill, str) and skill for skill in case["required_skills"])
