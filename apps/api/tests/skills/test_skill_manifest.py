# 文件说明：后端自动化测试：test_skill_manifest。
from pathlib import Path

import pytest

from app.skills.manifest import SkillManifestError
from app.skills.registry import SkillRegistry


def write_skill(
    root: Path,
    name: str = "route-optimization",
    *,
    allowed_tools: list[str] | None = None,
    extra_yaml: str = "",
) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    tools = allowed_tools or []
    tool_lines = "".join(f"  - {tool}\n" for tool in tools)
    manifest = skill_dir / "skill.yaml"
    manifest.write_text(
        (
            f"name: {name}\n"
            "version: 1.0.0\n"
            "status: active\n"
            "description: Build a feasible route order from verified places.\n"
            "allowed_tools:\n"
            f"{tool_lines}"
            "allowed_mcp_connectors: []\n"
            "max_tool_calls: 8\n"
            "timeout_seconds: 40\n"
            "max_tokens: 1200\n"
            "fallback: existing_itinerary_graph\n"
            f"{extra_yaml}"
        ),
        encoding="utf-8",
    )
    return manifest


def test_skill_manifest_rejects_unknown_tool(tmp_path: Path) -> None:
    write_skill(tmp_path, allowed_tools=["shell_exec"])

    with pytest.raises(SkillManifestError):
        SkillRegistry(known_tools={"search_places"}).load(tmp_path)
