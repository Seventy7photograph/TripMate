# 文件说明：Agent 受控工具：registry。
from dataclasses import dataclass
from typing import cast

from pydantic import BaseModel

from app.providers.llm.base import ToolDefinition
from app.tools.context import ToolContext
from app.tools.contracts import ToolHandler, ToolSpec


class ToolNotAllowedError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    spec: ToolSpec
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = RegisteredTool(spec=spec, handler=handler)

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._tools)

    def get(self, name: str) -> RegisteredTool:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotAllowedError(name)
        return tool

    def get_for_context(
        self,
        context: ToolContext,
        name: str,
    ) -> RegisteredTool:
        tool = self._tools.get(name)
        if (
            tool is None
            or name not in context.allowed_tools
            or tool.spec.provider_type not in context.provider_permissions
            or tool.spec.risk == "write"
        ):
            raise ToolNotAllowedError(name)
        return tool

    def openai_schemas(self, allowed_names: set[str]) -> list[ToolDefinition]:
        # 只暴露“已注册 Tool”和调用方 allowlist 的交集。
        definitions: list[ToolDefinition] = []
        for name in sorted(allowed_names):
            tool = self._tools.get(name)
            if tool is None:
                continue
            parameters = dict(tool.spec.input_model.model_json_schema())
            parameters["additionalProperties"] = False
            definitions.append(
                ToolDefinition(
                    name=tool.spec.name,
                    description=tool.spec.description,
                    parameters=parameters,
                )
            )
        return definitions

    async def invoke(
        self,
        context: ToolContext,
        name: str,
        payload: dict[str, object],
    ) -> BaseModel:
        # 名称、allowlist 和 Provider 权限全部通过后，才允许校验输入或执行 handler。
        tool = self.get_for_context(context, name)
        input_payload = tool.spec.input_model.model_validate(payload)
        result = await tool.handler(context, input_payload)
        if not isinstance(result, BaseModel):
            raise TypeError(f"Tool handler returned a non-model result: {name}")
        return cast(BaseModel, tool.spec.output_model.model_validate(result))
