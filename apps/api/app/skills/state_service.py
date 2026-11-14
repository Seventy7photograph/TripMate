# 文件说明：Skill 运行时：state_service。
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit_log import AdminAuditLog
from app.models.skill_state import SkillState
from app.skills.manifest import SkillManifest, SkillStatus
from app.skills.registry import SkillRegistry


@dataclass(frozen=True, slots=True)
class SkillView:
    name: str
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
        manifests = registry.latest_manifests()
        states = await self._state_map()
        return [
            manifest
            for manifest in manifests
            if _effective_enabled(manifest, states.get(manifest.name))
        ]

    async def skill_views(self, registry: SkillRegistry) -> list[SkillView]:
        manifests = registry.latest_manifests()
        states = await self._state_map()
        return [
            _skill_view(manifest, states.get(manifest.name))
            for manifest in manifests
        ]

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
) -> SkillView:
    state_matches = state is not None and state.version == manifest.version
    return SkillView(
        name=manifest.name,
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
