# 文件说明：Prompt 统一目录加载器。
from hashlib import sha256
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.prompts.schema import LoadedPrompt, PromptMetadata, PromptReference


class PromptCatalogError(Exception):
    pass


class PromptNotFoundError(PromptCatalogError):
    pass


class PromptCatalog:
    def __init__(self, root: Path) -> None:
        if root.is_symlink():
            raise PromptCatalogError("Prompt root cannot be a symbolic link")
        self.root = root.resolve()
        self._prompts: dict[tuple[str, str, str], LoadedPrompt] = {}
        self._load()

    def get(self, reference: PromptReference) -> LoadedPrompt:
        key = (reference.agent, reference.prompt_id, reference.version)
        prompt = self._prompts.get(key)
        if prompt is None:
            raise PromptNotFoundError(
                f"{reference.agent}/{reference.prompt_id}@{reference.version}"
            )
        return prompt

    def audit_records(self) -> list[dict[str, str]]:
        return [
            prompt.audit_record()
            for _, prompt in sorted(self._prompts.items())
        ]

    def _load(self) -> None:
        if not self.root.is_dir():
            raise PromptCatalogError("Prompt root must be a directory")

        loaded: dict[tuple[str, str, str], LoadedPrompt] = {}
        for prompt_path in self._prompt_paths():
            prompt = self._load_prompt(prompt_path)
            key = (prompt.agent, prompt.prompt_id, prompt.version)
            if key in loaded:
                raise PromptCatalogError(
                    f"Duplicate prompt: {prompt.agent}/{prompt.prompt_id}"
                    f"@{prompt.version}"
                )
            loaded[key] = prompt
        self._prompts = loaded

    def _prompt_paths(self) -> list[Path]:
        agents_root = self.root / "agents"
        if agents_root.is_symlink():
            raise PromptCatalogError(
                "Prompt agent directories cannot be symbolic links"
            )
        if not agents_root.is_dir():
            return []

        paths: list[Path] = []
        for agent_dir in sorted(agents_root.iterdir()):
            if agent_dir.is_symlink():
                raise PromptCatalogError(
                    "Prompt agent directories cannot be symbolic links"
                )
            if not agent_dir.is_dir():
                continue
            for prompt_dir in sorted(agent_dir.iterdir()):
                if prompt_dir.is_symlink():
                    raise PromptCatalogError(
                        "Prompt version directories cannot be symbolic links"
                    )
                if not prompt_dir.is_dir():
                    continue
                for prompt_path in sorted(prompt_dir.iterdir()):
                    if prompt_path.is_symlink():
                        raise PromptCatalogError(
                            "Prompt files cannot be symbolic links"
                        )
                    if prompt_path.is_file() and prompt_path.suffix == ".md":
                        paths.append(prompt_path)
        return paths

    def _load_prompt(self, prompt_path: Path) -> LoadedPrompt:
        resolved = prompt_path.resolve(strict=True)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise PromptCatalogError("Prompt escapes the catalog root") from exc

        raw_bytes = resolved.read_bytes()
        try:
            raw_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PromptCatalogError("Prompt must be UTF-8") from exc
        metadata_text, content = _split_front_matter(raw_text)
        try:
            raw_metadata = yaml.safe_load(metadata_text)
        except yaml.YAMLError as exc:
            raise PromptCatalogError("Prompt front matter YAML is invalid") from exc
        if not isinstance(raw_metadata, dict):
            raise PromptCatalogError("Prompt front matter must be a mapping")
        try:
            metadata = PromptMetadata.model_validate(raw_metadata)
        except ValidationError as exc:
            raise PromptCatalogError("Prompt metadata schema is invalid") from exc

        expected = (
            self.root
            / "agents"
            / metadata.agent
            / metadata.prompt_id
            / f"{metadata.version}.md"
        ).resolve()
        if resolved != expected:
            raise PromptCatalogError("Prompt path does not match its metadata")
        if not content.strip():
            raise PromptCatalogError("Prompt content cannot be empty")

        return LoadedPrompt(
            agent=metadata.agent,
            prompt_id=metadata.prompt_id,
            version=metadata.version,
            description=metadata.description,
            content=content.strip(),
            sha256=sha256(raw_bytes).hexdigest(),
        )


def prompt_request_metadata(
    prompt: LoadedPrompt,
    *,
    operation: str,
) -> dict[str, str]:
    return {
        "operation": operation,
        "prompt_agent": prompt.agent,
        "prompt_id": prompt.prompt_id,
        "prompt_version": prompt.version,
        "prompt_sha256": prompt.sha256,
    }


def _split_front_matter(text: str) -> tuple[str, str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise PromptCatalogError("Prompt must start with YAML front matter")
    end = normalized.find("\n---\n", 4)
    if end < 0:
        raise PromptCatalogError("Prompt front matter is not closed")
    return normalized[4:end], normalized[end + 5 :]
