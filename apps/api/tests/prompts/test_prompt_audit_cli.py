# 文件说明：后端自动化测试：Prompt 版本审计命令。
from pathlib import Path

from app.prompts.audit import audit_prompt_catalog
from app.prompts.catalog import PromptCatalog

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_prompt_audit_reports_agent_versions_and_inventory_status() -> None:
    report = audit_prompt_catalog(
        PromptCatalog(PROJECT_ROOT / "apps/api/prompts"),
        PROJECT_ROOT / "apps/api/prompts/INVENTORY.md",
    )

    assert report.prompt_count == 5
    assert report.agent_versions == {
        "itinerary-composer": ["system@1.0.0"],
        "requirement-parser": ["system@1.0.0"],
        "research-planner": ["tool-selection@1.0.0"],
        "travel-chat": ["answer@1.0.0", "intent-router@1.0.0"],
    }
    assert report.errors == []


def test_prompt_audit_fails_when_inventory_is_missing_an_entry(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "prompt-inventory.md"
    inventory.write_text("# Empty inventory\n", encoding="utf-8")

    report = audit_prompt_catalog(
        PromptCatalog(PROJECT_ROOT / "apps/api/prompts"),
        inventory,
    )

    assert len(report.errors) == 5
    assert all("not listed" in error for error in report.errors)
