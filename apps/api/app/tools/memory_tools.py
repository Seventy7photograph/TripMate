# 文件说明：Agent 受控工具：memory_tools。
"""读取用户明确授权旅行记忆的只读 Tool。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.services.memory_service import MemoryService
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec


class AuthorizedMemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=8, ge=1, le=20)


class MemoryItem(BaseModel):
    memory_id: str
    category: str
    content: str
    updated_at: datetime


class AuthorizedMemoryOutput(BaseModel):
    items: list[MemoryItem]
    applied_count: int
    degraded: bool = False
    write_performed: bool = False


_MEMORY_TOOL_SPEC = ToolSpec(
    name="get_authorized_memory_context",
    description="Read only enabled memories explicitly authorized by the owner.",
    input_model=AuthorizedMemoryInput,
    output_model=AuthorizedMemoryOutput,
    provider_type="memory",
    risk="read",
    timeout_seconds=5,
    max_retries=0,
)


class MemoryTool:
    name = _MEMORY_TOOL_SPEC.name

    def __init__(self, service: MemoryService, context: ToolContext) -> None:
        self._service = service
        self._context = context

    async def invoke(
        self,
        context: ToolContext,
        payload: BaseModel,
    ) -> BaseModel:
        # 归属用户只能来自 ToolContext，不能信任模型传入的参数。
        if context.owner_id is None:
            raise ValueError("owner_id is required for memory reads")
        owner_id = context.owner_id
        request = AuthorizedMemoryInput.model_validate(payload)
        memories = await context.runner.call(
            tool_name=self.name,
            provider="travel-memory",
            input_payload=request.model_dump(),
            operation=lambda: self._service.authorized_items(
                owner_id=owner_id,
                query=request.query,
                limit=request.limit,
            ),
            timeout_seconds=_MEMORY_TOOL_SPEC.timeout_seconds,
            max_retries=_MEMORY_TOOL_SPEC.max_retries,
        )
        items = [
            MemoryItem(
                memory_id=str(memory.id),
                category=str(memory.category),
                content=str(memory.content),
                updated_at=memory.updated_at,
            )
            for memory in memories
        ]
        return AuthorizedMemoryOutput(
            items=items,
            applied_count=len(items),
            degraded=False,
        )

    @staticmethod
    def spec() -> ToolSpec:
        return _MEMORY_TOOL_SPEC
