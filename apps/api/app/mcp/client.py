# 文件说明：官方 MCP SDK Streamable HTTP 客户端。

import asyncio
import time
from datetime import UTC, datetime
from typing import cast

from mcp import types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.mcp.gateway import McpToolExecutionError, McpTransportError
from app.mcp.models import McpConnectionState, McpRemoteResult


class OfficialMcpClient:
    async def call_tool(
        self,
        *,
        endpoint: str,
        tool_name: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> McpRemoteResult:
        try:
            async with asyncio.timeout(timeout_seconds):
                async with streamable_http_client(endpoint) as (
                    read_stream,
                    write_stream,
                ):
                    async with ClientSession(
                        read_stream,
                        write_stream,
                        read_timeout_seconds=timeout_seconds,
                    ) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            tool_name,
                            arguments=payload,
                            read_timeout_seconds=timeout_seconds,
                        )
        except TimeoutError as exc:
            raise McpTransportError("MCP request timed out") from exc
        except Exception as exc:
            raise McpTransportError("MCP transport failed") from exc
        if not isinstance(result, types.CallToolResult):
            raise McpToolExecutionError("MCP returned an unexpected response")
        return self.from_sdk_result(result)

    async def check_health(
        self,
        *,
        endpoint: str,
        timeout_seconds: float,
    ) -> McpConnectionState:
        started = time.perf_counter()
        try:
            async with asyncio.timeout(timeout_seconds):
                async with streamable_http_client(endpoint) as (
                    read_stream,
                    write_stream,
                ):
                    async with ClientSession(
                        read_stream,
                        write_stream,
                        read_timeout_seconds=timeout_seconds,
                    ) as session:
                        await session.initialize()
                        await session.list_tools()
        except TimeoutError as exc:
            raise McpTransportError("MCP health check timed out") from exc
        except Exception as exc:
            raise McpTransportError("MCP health check failed") from exc
        return McpConnectionState(
            connector_id="",
            enabled=True,
            status="healthy",
            latency_ms=max(
                1,
                int((time.perf_counter() - started) * 1_000),
            ),
            checked_at=datetime.now(UTC),
        )

    @staticmethod
    def from_sdk_result(result: types.CallToolResult) -> McpRemoteResult:
        content = [
            cast(
                dict[str, object],
                item.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude_none=True,
                ),
            )
            for item in result.content
        ]
        structured = result.structured_content
        if structured is not None and not isinstance(structured, dict):
            raise McpToolExecutionError("MCP structured output is not an object")
        return McpRemoteResult(
            content=content,
            structured_content=structured,
            is_error=bool(result.is_error),
        )
