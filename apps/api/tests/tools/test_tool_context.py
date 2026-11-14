# 文件说明：后端自动化测试：test_tool_context。
import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from app.tools.base import ToolRunner, ToolTimeoutError
from app.tools.context import ToolContext
from app.tools.contracts import ToolSpec
from app.tools.registry import ToolNotAllowedError, ToolRegistry


class NoopInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoopOutput(BaseModel):
    ok: bool = True


async def _noop_handler(
    context: ToolContext,
    payload: BaseModel,
) -> BaseModel:
    del context, payload
    return NoopOutput()


def test_tool_context_carries_identity_and_permissions() -> None:
    owner_id = uuid4()
    runner = ToolRunner(
        max_calls=2,
        deadline=datetime.now(UTC) + timedelta(seconds=5),
    )

    context = ToolContext(
        runner=runner,
        allowed_tools={"noop"},
        provider_permissions={"deterministic"},
        owner_id=owner_id,
    )

    assert context.runner is runner
    assert context.owner_id == owner_id
    assert "noop" in context.allowed_tools
    assert "deterministic" in context.provider_permissions


async def test_provider_permission_denial_fails_closed() -> None:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="noop",
            description="No-op deterministic tool.",
            input_model=NoopInput,
            output_model=NoopOutput,
            provider_type="external",
        ),
        _noop_handler,
    )
    context = ToolContext(
        runner=ToolRunner(
            max_calls=1,
            deadline=datetime.now(UTC) + timedelta(seconds=5),
        ),
        allowed_tools={"noop"},
        provider_permissions={"deterministic"},
        owner_id=uuid4(),
    )

    with pytest.raises(ToolNotAllowedError):
        await registry.invoke(context, "noop", {})


async def test_tool_runner_applies_tool_timeout_and_retry_limit() -> None:
    runner = ToolRunner(
        max_calls=1,
        deadline=datetime.now(UTC) + timedelta(seconds=5),
    )
    attempts = 0

    async def slow_operation() -> None:
        nonlocal attempts
        attempts += 1
        await asyncio.sleep(0.05)

    with pytest.raises(ToolTimeoutError):
        await runner.call(
            tool_name="slow",
            provider="test",
            input_payload={},
            operation=slow_operation,
            timeout_seconds=0.01,
            max_retries=0,
        )

    assert attempts == 1
    assert runner.audits[-1].error_code == "tool_timeout"


async def test_tool_runner_retries_operation_without_consuming_call_limit() -> None:
    runner = ToolRunner(
        max_calls=1,
        deadline=datetime.now(UTC) + timedelta(seconds=5),
    )
    attempts = 0

    async def flaky_operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient")
        return "ok"

    result = await runner.call(
        tool_name="flaky",
        provider="test",
        input_payload={},
        operation=flaky_operation,
        max_retries=1,
    )

    assert result == "ok"
    assert attempts == 2
    assert runner.call_count == 1
    assert runner.audits[-1].status == "success"
