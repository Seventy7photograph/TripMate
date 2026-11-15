# 文件说明：Skill 运行时：state_service。
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit_log import AdminAuditLog
from app.models.skill_state import SkillState
from app.skills.manifest import SkillManifest, SkillStatus
from app.skills.registry import SkillNotFoundError, SkillRegistry


@dataclass(frozen=True, slots=True)
class SkillView:
    name: str
    available_versions: list[str]
    version: str
    status: SkillStatus
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    allowed_tools: list[str]
    allowed_mcp_connectors: list[str]
    max_tool_calls: int
    timeout_seconds: float
    max_tokens: int
    fallback: str
    enabled: bool
    updated_by: UUID | None
    updated_at: datetime | None


class SkillStateService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set_enabled(
        self,
        *,
        skill_name: str,
        version: str,
        enabled: bool,
        actor_id: UUID,
        reason: str | None = None,
        default_enabled: bool = True,
    ) -> SkillState:
        model = await self._session.get(SkillState, skill_name)
        previous = (
            model.enabled
            if model is not None and model.version == version
            else default_enabled
        )
        if model is None:
            model = SkillState(
                skill_name=skill_name,
                version=version,
                enabled=enabled,
                updated_by=actor_id,
            )
            self._session.add(model)
        else:
            model.version = version
            model.enabled = enabled
            model.updated_by = actor_id
        self._session.add(
            AdminAuditLog(
                actor_id=actor_id,
                action="skill.toggle",
                target_type="skill",
                target_id=skill_name,
                details={
                    "version": version,
                    "previous_enabled": previous,
                    "enabled": enabled,
                    "reason": reason,
                },
            )
        )
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return model

    async def enabled_manifests(
        self,
        registry: SkillRegistry,
    ) -> list[SkillManifest]:
        states = await self._state_map()
        enabled: list[SkillManifest] = []
        for latest in registry.latest_manifests():
            state = states.get(latest.name)
            manifest = _selected_manifest(registry, latest, state)
            if _effective_enabled(manifest, state):
                enabled.append(manifest)
        return enabled

    async def skill_views(self, registry: SkillRegistry) -> list[SkillView]:
        states = await self._state_map()
        views: list[SkillView] = []
        for latest in registry.latest_manifests():
            state = states.get(latest.name)
            manifest = _selected_manifest(registry, latest, state)
            views.append(
                _skill_view(
                    manifest,
                    state,
                    available_versions=registry.versions(manifest.name),
                )
            )
        return views

    async def _state_map(self) -> dict[str, SkillState]:
        result = await self._session.execute(select(SkillState))
        return {state.skill_name: state for state in result.scalars()}


def _effective_enabled(
    manifest: SkillManifest,
    state: SkillState | None,
) -> bool:
    if manifest.status != "active":
        return False
    if state is None or state.version != manifest.version:
        return True
    return state.enabled


def _skill_view(
    manifest: SkillManifest,
    state: SkillState | None,
    *,
    available_versions: list[str],
) -> SkillView:
    state_matches = state is not None and state.version == manifest.version
    return SkillView(
        name=manifest.name,
        available_versions=available_versions,
        version=manifest.version,
        status=manifest.status,
        description=manifest.description,
        input_schema=manifest.input_schema,
        output_schema=manifest.output_schema,
        allowed_tools=list(manifest.allowed_tools),
        allowed_mcp_connectors=list(manifest.allowed_mcp_connectors),
        max_tool_calls=manifest.max_tool_calls,
        timeout_seconds=manifest.timeout_seconds,
        max_tokens=manifest.max_tokens,
        fallback=manifest.fallback,
        enabled=_effective_enabled(manifest, state),
        updated_by=state.updated_by if state_matches and state is not None else None,
        updated_at=state.updated_at if state_matches and state is not None else None,
    )


def _selected_manifest(
    registry: SkillRegistry,
    latest: SkillManifest,
    state: SkillState | None,
) -> SkillManifest:
    if state is None:
        return latest
    try:
        return registry.get(latest.name, state.version)
    except SkillNotFoundError:
        return latest
