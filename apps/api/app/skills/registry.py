# 文件说明：Skill 运行时：registry。
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.core.config import Settings
from app.skills.manifest import SkillManifest, SkillManifestError


class SkillNotFoundError(Exception):
    pass


class SkillRegistry:
    def __init__(self, known_tools: set[str]) -> None:
        self.known_tools = frozenset(known_tools)
        self._skills: dict[tuple[str, str], SkillManifest] = {}

    def load(self, root: Path) -> None:
        if root.is_symlink():
            raise SkillManifestError("Skill root cannot be a symbolic link")
        root_path = root.resolve()
        if not root_path.exists():
            return
        if not root_path.is_dir():
            raise SkillManifestError("Skill root must be a directory")

        loaded: dict[tuple[str, str], SkillManifest] = {}
        for skill_dir in sorted(root_path.iterdir()):
            if skill_dir.is_symlink():
                raise SkillManifestError("Skill directories cannot be symbolic links")
            if not skill_dir.is_dir():
                continue
            manifest_path = skill_dir / "skill.yaml"
            if not manifest_path.exists():
                continue
            if manifest_path.is_symlink():
                raise SkillManifestError("skill.yaml cannot be a symbolic link")
            manifest = self._load_manifest(manifest_path, root_path)
            if manifest.name != skill_dir.name:
                raise SkillManifestError(
                    f"Skill name does not match directory: {skill_dir.name}"
                )
            key = (manifest.name, manifest.version)
            if key in loaded:
                raise SkillManifestError(
                    f"Duplicate skill version: {manifest.name}@{manifest.version}"
                )
            loaded[key] = manifest
        self._skills = loaded

    def get(self, name: str, version: str | None = None) -> SkillManifest:
        if version is not None:
            manifest = self._skills.get((name, version))
            if manifest is None:
                raise SkillNotFoundError(f"{name}@{version}")
            return manifest

        versions = [
            manifest
            for (skill_name, _), manifest in self._skills.items()
            if skill_name == name
        ]
        if not versions:
            raise SkillNotFoundError(name)
        return max(versions, key=lambda item: _version_key(item.version))

    def latest_manifests(self) -> list[SkillManifest]:
        names = sorted({name for name, _ in self._skills})
        return [self.get(name) for name in names]

    def _load_manifest(
        self,
        manifest_path: Path,
        root: Path,
    ) -> SkillManifest:
        try:
            resolved = manifest_path.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise SkillManifestError("Skill manifest escapes the registry root") from exc

        try:
            raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise SkillManifestError("Skill manifest YAML is invalid") from exc
        if not isinstance(raw, dict):
            raise SkillManifestError("Skill manifest must be a mapping")

        try:
            manifest = SkillManifest.model_validate(raw)
        except ValidationError as exc:
            raise SkillManifestError("Skill manifest schema is invalid") from exc

        unknown_tools = set(manifest.allowed_tools) - self.known_tools
        if unknown_tools:
            raise SkillManifestError(
                f"Unknown tools: {', '.join(sorted(unknown_tools))}"
            )
        return manifest


def _version_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def load_configured_registry(settings: Settings) -> SkillRegistry:
    from app.tools.budget_tools import BudgetTool
    from app.tools.memory_tools import MemoryTool
    from app.tools.place_tools import PlaceTool
    from app.tools.route_tools import RouteTool

    registry = SkillRegistry(
        known_tools={
            PlaceTool.name,
            RouteTool.name,
            BudgetTool.name,
            MemoryTool.name,
            "get_weather",
            "search_nearby_places",
            "get_place_detail",
            "get_place_facts",
            "get_route_matrix",
            "get_altitude",
            "extract_attachment",
        }
    )
    registry.load(settings.skills_root)
    return registry
