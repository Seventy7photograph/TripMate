# 文件说明：MCP Gateway 安全异常与调用边界。

import json
import time
from typing import Protocol, cast

from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.mcp.models import (
    McpConnectionState,
    McpRemoteResult,
    McpToolResult,
)
from app.mcp.registry import McpConnectorRegistry, McpNotAllowedError
from app.services.prompt_safety import PromptSafetyService
from app.tools.context import ToolContext
from app.tools.registry import ToolNotAllowedError, ToolRegistry
from app.tools.weather_tools import WeatherSnapshotOutput


class McpClientError(Exception):
    code = "mcp_client_error"


class McpTransportError(McpClientError):
    code = "mcp_transport_error"


class McpToolExecutionError(McpClientError):
    code = "mcp_tool_error"


class McpClient(Protocol):
    async def call_tool(
        self,
        *,
        endpoint: str,
        tool_name: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> McpRemoteResult: ...

    async def check_health(
        self,
        *,
        endpoint: str,
        timeout_seconds: float,
    ) -> McpConnectionState: ...


class McpStateStore(Protocol):
    async def is_enabled(self, connector_id: str) -> bool: ...

    async def authorize_call(self, connector_id: str) -> None: ...

    async def record_success(
        self,
        connector_id: str,
        *,
        latency_ms: int,
    ) -> McpConnectionState: ...

    async def record_failure(
        self,
        connector_id: str,
        *,
        error_code: str,
    ) -> McpConnectionState: ...

    async def record_fallback(
        self,
        connector_id: str,
        *,
        error_code: str,
    ) -> McpConnectionState: ...


class McpGateway:
    def __init__(
        self,
        *,
        settings: Settings,
        connector_registry: McpConnectorRegistry,
        tool_registry: ToolRegistry,
        client: McpClient,
        state_store: McpStateStore,
    ) -> None:
        self._settings = settings
        self._connectors = connector_registry
        self._tools = tool_registry
        self._client = client
        self._state = state_store
        self._prompt_safety = PromptSafetyService()

    async def connect(self, url: str) -> McpConnectionState:
        definition = self._connectors.resolve_url(url)
        started = time.perf_counter()
        try:
            state = await self._client.check_health(
                endpoint=definition.endpoint,
                timeout_seconds=self._settings.mcp_timeout_seconds,
            )
        except Exception as exc:
            state = await self._state.record_failure(
                definition.connector_id,
                error_code=getattr(exc, "code", "mcp_transport_error"),
            )
            return state
        state = state.model_copy(
            update={
                "connector_id": definition.connector_id,
                "latency_ms": max(
                    state.latency_ms,
                    int((time.perf_counter() - started) * 1_000),
                ),
            }
        )
        return await self._state.record_success(
            definition.connector_id,
            latency_ms=state.latency_ms,
        )

    async def call_tool(
        self,
        context: ToolContext,
        connector: str,
        tool_name: str,
        payload: dict[str, object],
    ) -> McpToolResult:
        definition = self._connectors.resolve(connector)
        if definition.connector_id not in context.allowed_mcp_connectors:
            raise McpNotAllowedError(connector)
        binding = next(
            (
                item
                for item in definition.tools
                if item.name == tool_name
            ),
            None,
        )
        if binding is None:
            raise McpNotAllowedError(tool_name)
        try:
            registered = self._tools.get_for_context(context, tool_name)
        except ToolNotAllowedError as exc:
            raise McpNotAllowedError(tool_name) from exc
        if registered.spec.provider_type != binding.provider_type:
            raise McpNotAllowedError(tool_name)
        if not await self._state.is_enabled(definition.connector_id):
            fallback = await self._tools.invoke(
                context,
                tool_name,
                registered.spec.input_model.model_validate(
                    payload
                ).model_dump(mode="json"),
            )
            fallback_result = self._fallback_result(
                definition.connector_id,
                tool_name,
                fallback,
            )
            await self._record_fallback(
                definition.connector_id,
                "mcp_connector_disabled",
            )
            return fallback_result

        input_model = registered.spec.input_model.model_validate(payload)
        serialized_payload = input_model.model_dump(mode="json")
        started = time.perf_counter()
        try:
            result = await context.runner.call(
                tool_name=tool_name,
                provider=f"mcp:{definition.connector_id}",
                input_payload=serialized_payload,
                operation=lambda: self._execute_remote(
                    endpoint=definition.endpoint,
                    connector_id=definition.connector_id,
                    tool_name=tool_name,
                    payload=serialized_payload,
                    output_model=(
                        WeatherSnapshotOutput
                        if binding.output_kind == "weather_snapshot"
                        else registered.spec.output_model
                    ),
                ),
                timeout_seconds=min(
                    registered.spec.timeout_seconds,
                    self._settings.mcp_timeout_seconds,
                ),
                max_retries=0,
            )
        except McpClientError as exc:
            await self._state.record_failure(
                definition.connector_id,
                error_code=exc.code,
            )
            try:
                fallback = await self._tools.invoke(
                    context,
                    tool_name,
                    serialized_payload,
                )
            except Exception:
                raise exc
            fallback_result = self._fallback_result(
                definition.connector_id,
                tool_name,
                fallback,
            )
            await self._record_fallback(
                definition.connector_id,
                exc.code,
            )
            return fallback_result
        except Exception as exc:
            await self._state.record_failure(
                definition.connector_id,
                error_code=getattr(exc, "code", "mcp_tool_error"),
            )
            raise
        latency_ms = max(1, int((time.perf_counter() - started) * 1_000))
        await self._state.record_success(
            definition.connector_id,
            latency_ms=latency_ms,
        )
        return cast(McpToolResult, result)

    def _fallback_result(
        self,
        connector_id: str,
        tool_name: str,
        fallback: BaseModel,
    ) -> McpToolResult:
        return McpToolResult(
            connector_id=connector_id,
            tool_name=tool_name,
            prompt_text=self._prompt_safety.wrap_untrusted(
                f"fallback:{connector_id}:{tool_name}",
                json.dumps(
                    fallback.model_dump(mode="json"),
                    ensure_ascii=False,
                    default=str,
                ),
            ),
            data=fallback.model_dump(mode="json"),
            fallback_used=True,
        )

    async def _record_fallback(
        self,
        connector_id: str,
        error_code: str,
    ) -> None:
        record_fallback = getattr(self._state, "record_fallback", None)
        if record_fallback is not None:
            await record_fallback(
                connector_id,
                error_code=error_code,
            )

    async def _execute_remote(
        self,
        *,
        endpoint: str,
        connector_id: str,
        tool_name: str,
        payload: dict[str, object],
        output_model: type[BaseModel],
    ) -> BaseModel:
        await self._state.authorize_call(connector_id)
        remote = await self._client.call_tool(
            endpoint=endpoint,
            tool_name=tool_name,
            payload=payload,
            timeout_seconds=self._settings.mcp_timeout_seconds,
        )
        if remote.is_error:
            raise McpToolExecutionError(tool_name)
        validated = _validated_output(remote, output_model)
        wrapped = self._prompt_safety.wrap_untrusted(
            f"mcp:{connector_id}:{tool_name}",
            json.dumps(
                {
                    "content": remote.content,
                    "structured_content": remote.structured_content,
                },
                ensure_ascii=False,
                default=str,
            ),
        )
        return McpToolResult(
            connector_id=connector_id,
            tool_name=tool_name,
            content=remote.content,
            prompt_text=wrapped,
            data=validated.model_dump(mode="json"),
        )


def _validated_output(
    remote: McpRemoteResult,
    output_model: type[BaseModel],
) -> BaseModel:
    candidate: object | None = remote.structured_content
    if candidate is None:
        for item in remote.content:
            if item.get("type") != "text":
                continue
            raw_text = item.get("text")
            if not isinstance(raw_text, str):
                continue
            try:
                candidate = json.loads(raw_text)
            except ValueError as exc:
                raise McpToolExecutionError("invalid MCP JSON output") from exc
            break
    if not isinstance(candidate, dict):
        raise McpToolExecutionError("MCP output is missing structured data")
    try:
        return output_model.model_validate(candidate)
    except ValidationError as exc:
        raise McpToolExecutionError("invalid MCP structured output") from exc


__all__ = [
    "McpClientError",
    "McpGateway",
    "McpNotAllowedError",
    "McpToolExecutionError",
    "McpTransportError",
]
