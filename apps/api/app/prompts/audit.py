# 文件说明：Prompt Catalog 与位置清单一致性审计。
from dataclasses import dataclass
from pathlib import Path

from app.prompts.catalog import PromptCatalog


@dataclass(frozen=True, slots=True)
class PromptAuditReport:
    prompt_count: int
    agent_versions: dict[str, list[str]]
    prompts: list[dict[str, str]]
    errors: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "prompt_count": self.prompt_count,
            "agent_versions": self.agent_versions,
            "prompts": self.prompts,
            "errors": self.errors,
        }


def audit_prompt_catalog(
    catalog: PromptCatalog,
    inventory_path: Path,
) -> PromptAuditReport:
    prompts = catalog.audit_records()
    inventory = (
        inventory_path.read_text(encoding="utf-8")
        if inventory_path.is_file()
        else ""
    )
    agent_versions: dict[str, list[str]] = {}
    errors: list[str] = []
    for prompt in prompts:
        agent_versions.setdefault(prompt["agent"], []).append(
            f"{prompt['prompt_id']}@{prompt['version']}"
        )
        relative_path = (
            f"apps/api/prompts/agents/{prompt['agent']}/"
            f"{prompt['prompt_id']}/{prompt['version']}.md"
        )
        if relative_path not in inventory:
            errors.append(f"{relative_path} is not listed in prompt inventory")
    for versions in agent_versions.values():
        versions.sort()
    return PromptAuditReport(
        prompt_count=len(prompts),
        agent_versions=agent_versions,
        prompts=prompts,
        errors=errors,
    )
