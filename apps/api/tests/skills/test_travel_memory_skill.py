# 文件说明：后端自动化测试：travel-memory Skill 只读权限。
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.core.config import Settings
from app.skills.executor import SkillContext, SkillExecutor
from app.skills.production import TravelMemoryInput, production_skill_handlers
from app.skills.registry import load_configured_registry
from app.tools.base import ToolRunner
from app.tools.context import ToolContext
from app.tools.memory_tools import MemoryTool
from app.tools.registry import ToolRegistry


class StubMemoryService:
    async def authorized_items(self, *, owner_id, query, limit):
        del owner_id, query, limit
        return [
            SimpleNamespace(
                id=uuid4(),
                category="lodging",
                content="住宿优先靠近地铁站",
                updated_at=datetime.now(UTC),
            )
        ]


async def test_memory_skill_only_reads_authorized_memory() -> None:
    context = ToolContext(
        runner=ToolRunner(
            max_calls=2,
            deadline=datetime.now(UTC) + timedelta(seconds=10),
        ),
        allowed_tools={"get_authorized_memory_context"},
        provider_permissions={"memory"},
        owner_id=uuid4(),
    )
    tools = ToolRegistry()
    memory_tool = MemoryTool(StubMemoryService(), context)  # type: ignore[arg-type]
    tools.register(MemoryTool.spec(), memory_tool.invoke)
    skills = load_configured_registry(Settings(app_env="test"))
    manifest = skills.get("travel-memory")
    handlers = production_skill_handlers(tools, context)

    result = await SkillExecutor().execute(
        manifest,
        SkillContext(
            tool_registry=tools,
            tool_context=context,
            handler=handlers[manifest.name],
        ),
        TravelMemoryInput(query="住宿偏好"),
    )

    assert result.output.applied_count == 1
    assert result.output.write_performed is False
    assert set(result.allowed_tools) == {"get_authorized_memory_context"}
