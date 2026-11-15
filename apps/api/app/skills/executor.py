# 文件说明：Skill 运行时：executor。
import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Literal, cast

from jsonschema import ValidationError as JsonSchemaValidationError  # type: ignore[import-untyped]
from jsonschema import validate as validate_json_schema  # type: ignore[import-untyped]
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
    def __init__(
        self,
        code: str,
        message: str,
        fallback: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.fallback = fallback


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
        input_data: BaseModel | dict[str, object],
        max_tokens: int | None = None,
    ) -> SkillExecutionResult:
        # 所有权限检查均在已审核 handler 执行前失败关闭。
        if skill.status != "active":
            raise SkillExecutionError(
                "skill_disabled",
                "Skill is disabled",
                fallback=skill.fallback,
            )
        missing_permissions = set(skill.allowed_tools) - set(
            context.tool_context.allowed_tools
        )
        if missing_permissions:
            raise SkillExecutionError(
                "skill_tool_not_allowed",
                "Skill requests tools outside the supplied allowlist",
                fallback=skill.fallback,
            )
        if (
            context.tool_context.allowed_mcp_connectors
            and not set(skill.allowed_mcp_connectors).issubset(
                context.tool_context.allowed_mcp_connectors
            )
        ):
            raise SkillExecutionError(
                "skill_mcp_not_allowed",
                "Skill requests MCP connectors outside the supplied allowlist",
                fallback=skill.fallback,
            )
        for tool_name in skill.allowed_tools:
            try:
                context.tool_registry.get(tool_name)
            except ToolNotAllowedError as exc:
                raise SkillExecutionError(
                    "skill_tool_not_allowed",
                    "Skill requests a tool that is not registered",
                    fallback=skill.fallback,
                ) from exc
        if context.handler is None:
            raise SkillExecutionError(
                "skill_handler_missing",
                "No reviewed handler is configured for this skill",
                fallback=skill.fallback,
            )

        input_payload = _input_payload(input_data)
        try:
            validate_json_schema(
                instance=input_payload,
                schema=skill.input_schema,
            )
        except JsonSchemaValidationError as exc:
            raise SkillExecutionError(
                "skill_input_schema_invalid",
                "Skill input does not match the reviewed manifest schema",
                fallback=skill.fallback,
            ) from exc

        # 子 Runner 执行 Skill 自己的 Tool 预算，同时共享父级总时限和审计。
        scoped_context = replace(
            context.tool_context,
            runner=context.tool_context.runner.scoped(
                max_calls=skill.max_tool_calls
            ),
            allowed_tools=frozenset(skill.allowed_tools),
            allowed_mcp_connectors=frozenset(
                set(skill.allowed_mcp_connectors)
                & set(context.tool_context.allowed_mcp_connectors)
            ),
        )
        try:
            async with asyncio.timeout(skill.timeout_seconds):
                output = await context.handler(
                    skill,
                    scoped_context,
                    cast(BaseModel, input_data),
                )
        except TimeoutError as exc:
            raise SkillExecutionError(
                "skill_timeout",
                "Skill execution exceeded its timeout",
                fallback=skill.fallback,
            ) from exc
        if not isinstance(output, BaseModel):
            raise SkillExecutionError(
                "skill_output_invalid",
                "Skill handler returned a non-model output",
                fallback=skill.fallback,
            )
        output_payload = output.model_dump(mode="json")
        try:
            validate_json_schema(
                instance=output_payload,
                schema=skill.output_schema,
            )
        except JsonSchemaValidationError as exc:
            raise SkillExecutionError(
                "skill_output_schema_invalid",
                "Skill output does not match the reviewed manifest schema",
                fallback=skill.fallback,
            ) from exc
        if skill.requires_evidence and not _contains_evidence(output_payload):
            raise SkillExecutionError(
                "skill_evidence_required",
                "Skill output does not contain Evidence identifiers",
                fallback=skill.fallback,
            )
        estimated_tokens = max(
            1,
            (
                len(
                    json.dumps(
                        output_payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                + 1
            )
            // 2,
        )
        effective_max_tokens = (
            min(skill.max_tokens, max_tokens)
            if max_tokens is not None
            else skill.max_tokens
        )
        if estimated_tokens > effective_max_tokens:
            raise SkillExecutionError(
                "skill_output_budget_exceeded",
                "Skill output exceeds the reviewed output budget",
                fallback=skill.fallback,
            )
        return SkillExecutionResult(
            skill_name=skill.name,
            version=skill.version,
            status="completed",
            output=output,
            allowed_tools=tuple(skill.allowed_tools),
            allowed_mcp_connectors=tuple(skill.allowed_mcp_connectors),
            tool_calls=scoped_context.runner.call_count,
            max_tokens=effective_max_tokens,
        )


def _input_payload(input_data: BaseModel | dict[str, object]) -> dict[str, object]:
    if isinstance(input_data, BaseModel):
        return input_data.model_dump(mode="json", exclude_unset=True)
    return dict(input_data)


def _contains_evidence(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"evidence_id", "evidence_ids"}:
                if isinstance(item, list) and item:
                    return True
                if item is not None:
                    return True
            if _contains_evidence(item):
                return True
    elif isinstance(value, list):
        return any(_contains_evidence(item) for item in value)
    return False
