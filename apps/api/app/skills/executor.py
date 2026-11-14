# 文件说明：Skill 运行时：executor。
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Literal

from pydantic import BaseModel

from app.skills.manifest import SkillManifest
from app.tools.context import ToolContext
from app.tools.registry import ToolNotAllowedError, ToolRegistry

SkillExecutionStatus = Literal["completed", "failed"]
SkillHandler = Callable[
    [SkillManifest, ToolContext, BaseModel],
    Awaitable[BaseModel],
]


class SkillExecutionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class SkillContext:
    tool_registry: ToolRegistry
    tool_context: ToolContext
    handler: SkillHandler | None = None


@dataclass(frozen=True, slots=True)
class SkillExecutionResult:
    skill_name: str
    version: str
    status: SkillExecutionStatus
    output: BaseModel
    allowed_tools: tuple[str, ...]
    allowed_mcp_connectors: tuple[str, ...]
    tool_calls: int
    max_tokens: int


class SkillExecutor:
    async def execute(
        self,
        skill: SkillManifest,
        context: SkillContext,
        input_data: BaseModel,
    ) -> SkillExecutionResult:
        # 所有权限检查均在已审核 handler 执行前失败关闭。
        if skill.status != "active":
            raise SkillExecutionError("skill_disabled", "Skill is disabled")
        missing_permissions = set(skill.allowed_tools) - set(
            context.tool_context.allowed_tools
        )
        if missing_permissions:
            raise SkillExecutionError(
                "skill_tool_not_allowed",
                "Skill requests tools outside the supplied allowlist",
            )
        missing_connectors = set(skill.allowed_mcp_connectors) - set(
            context.tool_context.allowed_mcp_connectors
        )
        if missing_connectors:
            raise SkillExecutionError(
                "skill_mcp_not_allowed",
                "Skill requests MCP connectors outside the supplied allowlist",
            )
        for tool_name in skill.allowed_tools:
            try:
                context.tool_registry.get(tool_name)
            except ToolNotAllowedError as exc:
                raise SkillExecutionError(
                    "skill_tool_not_allowed",
                    "Skill requests a tool that is not registered",
                ) from exc
        if context.handler is None:
            raise SkillExecutionError(
                "skill_handler_missing",
                "No reviewed handler is configured for this skill",
            )

        # 子 Runner 执行 Skill 自己的 Tool 预算，同时共享父级总时限和审计。
        scoped_context = replace(
            context.tool_context,
            runner=context.tool_context.runner.scoped(
                max_calls=skill.max_tool_calls
            ),
            allowed_tools=frozenset(skill.allowed_tools),
            allowed_mcp_connectors=frozenset(
                skill.allowed_mcp_connectors
            ),
        )
        try:
            async with asyncio.timeout(skill.timeout_seconds):
                output = await context.handler(
                    skill,
                    scoped_context,
                    input_data,
                )
        except TimeoutError as exc:
            raise SkillExecutionError(
                "skill_timeout",
                "Skill execution exceeded its timeout",
            ) from exc
        if not isinstance(output, BaseModel):
            raise SkillExecutionError(
                "skill_output_invalid",
                "Skill handler returned a non-model output",
            )
        return SkillExecutionResult(
            skill_name=skill.name,
            version=skill.version,
            status="completed",
            output=output,
            allowed_tools=tuple(skill.allowed_tools),
            allowed_mcp_connectors=tuple(skill.allowed_mcp_connectors),
            tool_calls=scoped_context.runner.call_count,
            max_tokens=skill.max_tokens,
        )
