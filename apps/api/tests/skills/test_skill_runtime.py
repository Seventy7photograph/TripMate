# 文件说明：后端自动化测试：统一 Skill Runtime 的真实注册与执行边界。
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.main import app
from app.skills.runtime import build_skill_runtime


async def test_runtime_registers_every_manifest_handler_and_tool(
    api_client: httpx.AsyncClient,
) -> None:
    del api_client
    runtime = await build_skill_runtime(
        session=app.state.test_session,
        settings=get_settings(),
        owner_id=uuid4(),
    )

    report = runtime.integrity_report()

    assert report.manifest_count == 12
    assert report.missing_handlers == []
    assert report.missing_tools == []
    assert report.missing_mcp_connectors == []


async def test_runtime_executes_budget_skill_through_registered_tool(
    api_client: httpx.AsyncClient,
) -> None:
    del api_client
    runtime = await build_skill_runtime(
        session=app.state.test_session,
        settings=get_settings(),
        owner_id=uuid4(),
    )

    result = await runtime.execute(
        "budget-optimization",
        {
            "stop_costs_minor": [10_000, 20_000],
            "budget_minor": 50_000,
        },
    )

    assert result.status == "completed"
    assert "calculate_budget" in runtime.tool_context.runner.audits[0].tool_name


async def test_runtime_closes_all_owned_provider_clients(
    api_client: httpx.AsyncClient,
) -> None:
    del api_client
    closed: list[str] = []

    class Closeable:
        async def close(self) -> None:
            closed.append("closed")

    runtime = await build_skill_runtime(
        session=app.state.test_session,
        settings=get_settings(),
        owner_id=uuid4(),
    )
    runtime.closeables = (Closeable(),)

    await runtime.close()

    assert closed == ["closed"]
