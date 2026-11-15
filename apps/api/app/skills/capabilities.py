# 文件说明：构建 Admin 使用的真实 Skill 运行能力与近期执行快照。
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.agent_run import AgentRun
from app.skills.metadata import SKILL_METADATA
from app.skills.runtime import build_skill_runtime
from app.skills.state_service import SkillStateService


@dataclass(frozen=True, slots=True)
class SkillCapabilitySnapshot:
    name: str
    available_versions: list[str]
    display_name: str
    purpose: str
    boundary: str
    surfaces: list[str]
    version: str
    status: Literal["active", "disabled"]
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
    registered: bool
    runtime_status: Literal["ready", "degraded", "disabled", "unavailable"]
    execution_mode: Literal["mcp", "local", "disabled"]
    recent_runs: int
    success_rate: float | None
    last_used_at: datetime | None
    as_of: datetime


async def skill_capability_snapshots(
    *,
    session: AsyncSession,
    settings: Settings,
    owner_id: UUID,
) -> list[SkillCapabilitySnapshot]:
    runtime = await build_skill_runtime(
        session=session,
        settings=settings,
        owner_id=owner_id,
    )
    try:
        integrity = runtime.integrity_report()
        views = await SkillStateService(session).skill_views(runtime.registry)
        now = datetime.now(UTC)
        metrics = await _recent_metrics(
            session,
            since=now - timedelta(hours=24),
        )
        configured_mcp = set(runtime.tool_context.allowed_mcp_connectors)
        snapshots: list[SkillCapabilitySnapshot] = []
        for view in views:
            metadata = SKILL_METADATA.get(
                view.name,
                SKILL_METADATA["trip-intent-routing"],
            )
            missing_tools = [
                tool
                for tool in view.allowed_tools
                if tool in integrity.missing_tools
            ]
            registered = (
                view.name not in integrity.missing_handlers
            )
            mcp_ready = all(
                connector in configured_mcp
                for connector in view.allowed_mcp_connectors
            )
            execution_mode: Literal["mcp", "local", "disabled"]
            if not view.enabled:
                execution_mode = "disabled"
            elif view.allowed_mcp_connectors and mcp_ready:
                execution_mode = "mcp"
            else:
                execution_mode = "local"
            runtime_status: Literal[
                "ready",
                "degraded",
                "disabled",
                "unavailable",
            ]
            if not view.enabled:
                runtime_status = "disabled"
            elif not registered or missing_tools:
                runtime_status = "unavailable"
            elif view.allowed_mcp_connectors and not mcp_ready:
                runtime_status = "degraded"
            else:
                runtime_status = "ready"
            metric = metrics.get(view.name, {})
            snapshots.append(
                SkillCapabilitySnapshot(
                    name=view.name,
                available_versions=view.available_versions,
                    display_name=metadata.display_name,
                    purpose=metadata.purpose,
                    boundary=metadata.boundary,
                    surfaces=list(metadata.surfaces),
                    version=view.version,
                    status=view.status,
                    description=view.description,
                    input_schema=view.input_schema,
                    output_schema=view.output_schema,
                    allowed_tools=view.allowed_tools,
                    allowed_mcp_connectors=view.allowed_mcp_connectors,
                    max_tool_calls=view.max_tool_calls,
                    timeout_seconds=view.timeout_seconds,
                    max_tokens=view.max_tokens,
                    fallback=view.fallback,
                    enabled=view.enabled,
                    updated_by=view.updated_by,
                    updated_at=view.updated_at,
                    registered=registered,
                    runtime_status=runtime_status,
                    execution_mode=execution_mode,
                    recent_runs=int(str(metric.get("runs", 0))),
                    success_rate=cast(
                        float | None,
                        metric.get("success_rate"),
                    ),
                    last_used_at=cast(
                        datetime | None,
                        metric.get("last_used_at"),
                    ),
                    as_of=now,
                )
            )
        return snapshots
    finally:
        await runtime.close()


async def _recent_metrics(
    session: AsyncSession,
    *,
    since: datetime,
) -> dict[str, dict[str, object]]:
    rows = (
        await session.execute(
            select(
                AgentRun.status,
                AgentRun.skills_used,
                AgentRun.created_at,
            )
            .where(
                AgentRun.created_at >= since,
                AgentRun.provider != "mock",
            )
            .order_by(AgentRun.created_at.desc())
            .limit(500)
        )
    ).all()
    counts: dict[str, int] = defaultdict(int)
    successes: dict[str, int] = defaultdict(int)
    last_used: dict[str, datetime] = {}
    for status, skills_used, created_at in rows:
        for item in skills_used:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            counts[name] += 1
            if status in {"completed", "partial"}:
                successes[name] += 1
            previous = last_used.get(name)
            if previous is None or created_at > previous:
                last_used[name] = created_at
    return {
        name: {
            "runs": counts[name],
            "success_rate": successes[name] / counts[name],
            "last_used_at": last_used.get(name),
        }
        for name in counts
    }
