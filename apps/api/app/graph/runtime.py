# 文件说明：LangGraph 编排：runtime。
from collections.abc import Collection, Mapping
from datetime import UTC, datetime
from uuid import UUID

from app.schemas.ai import PlanningEventContract
from app.tools.base import ToolRunner
from app.tools.context import EvidenceWriter, ToolContext
from app.tools.registry import ToolRegistry


class GraphRuntime:
    def __init__(
        self,
        *,
        max_tool_calls: int,
        deadline: datetime,
        owner_id: UUID | None = None,
        evidence_writer: EvidenceWriter | None = None,
        allowed_tools: Collection[str] = (),
        provider_permissions: Collection[str] = (),
    ) -> None:
        self.deadline = deadline
        self.tools = ToolRunner(max_calls=max_tool_calls, deadline=deadline)
        self.tool_context = ToolContext(
            runner=self.tools,
            allowed_tools=frozenset(allowed_tools),
            provider_permissions=frozenset(provider_permissions),
            owner_id=owner_id,
            evidence_writer=evidence_writer,
        )
        self.tool_registry = ToolRegistry()
        self._events: list[PlanningEventContract] = []
        self._started_at = datetime.now(UTC)

    @property
    def events(self) -> list[PlanningEventContract]:
        return list(self._events)

    def emit(
        self,
        event_type: str,
        *,
        message: str,
        stage: str | None = None,
        status: str | None = None,
        tool_name: str | None = None,
        provider: str | None = None,
        payload: Mapping[str, object] | None = None,
    ) -> None:
        self._events.append(
            PlanningEventContract(
                sequence=len(self._events) + 1,
                type=event_type,  # type: ignore[arg-type]
                stage=stage,
                message=message,
                status=status,
                tool_name=tool_name,
                provider=provider,
                payload=dict(payload or {}),
            )
        )

    def event_dicts(self) -> list[dict[str, object]]:
        return [event.model_dump(mode="json") for event in self._events]

    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.deadline

    @property
    def elapsed_ms(self) -> int:
        return int((datetime.now(UTC) - self._started_at).total_seconds() * 1_000)
