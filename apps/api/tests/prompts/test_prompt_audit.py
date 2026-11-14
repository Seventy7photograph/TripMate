# 文件说明：后端自动化测试：test_prompt_audit。
from pathlib import Path

from app.prompts.catalog import PromptCatalog
from app.prompts.schema import PromptReference

PROJECT_ROOT = Path(__file__).resolve().parents[4]
INVENTORY = PROJECT_ROOT / "apps/api/prompts/INVENTORY.md"


def test_every_agent_prompt_is_versioned_and_listed_in_inventory() -> None:
    catalog = PromptCatalog(PROJECT_ROOT / "apps/api/prompts")

    assert catalog.audit_records() == [
        {
            "agent": "itinerary-composer",
            "prompt_id": "system",
            "version": "1.0.0",
            "sha256": catalog.get(
                catalog_reference("itinerary-composer", "system", "1.0.0")
            ).sha256,
        },
        {
            "agent": "requirement-parser",
            "prompt_id": "system",
            "version": "1.0.0",
            "sha256": catalog.get(
                catalog_reference("requirement-parser", "system", "1.0.0")
            ).sha256,
        },
        {
            "agent": "research-planner",
            "prompt_id": "tool-selection",
            "version": "1.0.0",
            "sha256": catalog.get(
                catalog_reference("research-planner", "tool-selection", "1.0.0")
            ).sha256,
        },
        {
            "agent": "travel-chat",
            "prompt_id": "answer",
            "version": "1.0.0",
            "sha256": catalog.get(
                catalog_reference("travel-chat", "answer", "1.0.0")
            ).sha256,
        },
        {
            "agent": "travel-chat",
            "prompt_id": "intent-router",
            "version": "1.0.0",
            "sha256": catalog.get(
                catalog_reference("travel-chat", "intent-router", "1.0.0")
            ).sha256,
        },
    ]

    inventory = INVENTORY.read_text(encoding="utf-8")
    for record in catalog.audit_records():
        relative_path = (
            f"apps/api/prompts/agents/{record['agent']}/"
            f"{record['prompt_id']}/{record['version']}.md"
        )
        assert relative_path in inventory
        assert record["version"] in inventory


def test_agent_modules_do_not_embed_static_system_prompts() -> None:
    agent_dir = PROJECT_ROOT / "apps/api/app/agents"
    forbidden = (
        "_SYSTEM_PROMPT =",
        "_TOOL_SYSTEM_PROMPT =",
        "_LLM_SYSTEM_PROMPT =",
    )

    for path in agent_dir.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in source, f"{path.name} embeds {marker}"


def catalog_reference(
    agent: str,
    prompt_id: str,
    version: str,
) -> PromptReference:
    return PromptReference(
        agent=agent,
        prompt_id=prompt_id,
        version=version,
    )
