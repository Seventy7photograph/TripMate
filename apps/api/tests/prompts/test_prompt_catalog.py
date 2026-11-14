# 文件说明：后端自动化测试：test_prompt_catalog。
from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.prompts.catalog import PromptCatalog, PromptCatalogError
from app.prompts.schema import PromptReference


def write_prompt(
    root: Path,
    *,
    agent: str = "travel-chat",
    prompt_id: str = "intent-router",
    version: str = "1.0.0",
    content: str = "You are TripMate's travel intent router.",
) -> Path:
    prompt_dir = root / "agents" / agent / prompt_id
    prompt_dir.mkdir(parents=True)
    prompt_path = prompt_dir / f"{version}.md"
    prompt_path.write_text(
        (
            "---\n"
            "schema_version: 1\n"
            f"agent: {agent}\n"
            f"prompt_id: {prompt_id}\n"
            f"version: {version}\n"
            "description: Travel intent routing policy\n"
            "---\n"
            f"{content}\n"
        ),
        encoding="utf-8",
    )
    return prompt_path


def test_catalog_loads_versioned_markdown_with_digest(tmp_path: Path) -> None:
    prompt_path = write_prompt(tmp_path)
    reference = PromptReference(
        agent="travel-chat",
        prompt_id="intent-router",
        version="1.0.0",
    )

    prompt = PromptCatalog(tmp_path).get(reference)

    assert prompt.content == "You are TripMate's travel intent router."
    assert prompt.audit_record() == {
        "agent": "travel-chat",
        "prompt_id": "intent-router",
        "version": "1.0.0",
        "sha256": sha256(prompt_path.read_bytes()).hexdigest(),
    }


@pytest.mark.parametrize(
    ("agent", "prompt_id", "version"),
    [
        ("../outside", "system", "1.0.0"),
        ("travel-chat", "../../secret", "1.0.0"),
        ("travel-chat", "system", "../1.0.0"),
        ("travel-chat", "system", "latest"),
    ],
)
def test_prompt_reference_rejects_unsafe_segments(
    agent: str,
    prompt_id: str,
    version: str,
) -> None:
    with pytest.raises(ValidationError):
        PromptReference(
            agent=agent,
            prompt_id=prompt_id,
            version=version,
        )


def test_catalog_rejects_metadata_path_mismatch(tmp_path: Path) -> None:
    prompt_path = write_prompt(tmp_path)
    prompt_path.write_text(
        prompt_path.read_text(encoding="utf-8").replace(
            "prompt_id: intent-router",
            "prompt_id: answer",
        ),
        encoding="utf-8",
    )

    with pytest.raises(PromptCatalogError, match="metadata"):
        PromptCatalog(tmp_path)


def test_catalog_rejects_symbolic_link_escape(tmp_path: Path) -> None:
    root = tmp_path / "prompts"
    outside = root.parent / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    target = root / "agents" / "travel-chat" / "intent-router" / "1.0.0.md"
    target.parent.mkdir(parents=True)
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("Symbolic links are unavailable")

    with pytest.raises(PromptCatalogError, match="symbolic"):
        PromptCatalog(root)


def test_catalog_rejects_symbolic_link_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "prompts"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links are unavailable")

    with pytest.raises(PromptCatalogError, match="symbolic"):
        PromptCatalog(linked)
