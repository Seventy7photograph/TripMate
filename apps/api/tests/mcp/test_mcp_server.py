# 文件说明：后端自动化测试：真实 Streamable HTTP MCP 协议调用。
import asyncio
import socket
from contextlib import suppress
from datetime import UTC, datetime
from datetime import date as Date
from uuid import UUID

import uvicorn

from app.core.config import Settings
from app.evidence.draft import EvidenceDraft
from app.evidence.repository import EvidenceRepository
from app.main import app
from app.mcp.client import OfficialMcpClient
from app.mcp.server import create_amap_mcp_server, create_weather_mcp_server
from app.providers.mock_map import MockMapProvider
from app.providers.weather import WeatherSnapshot
from app.services.mcp_connector_service import McpConnectorService
from app.skills.runtime import build_skill_runtime
from tests.test_auth import register_user


async def test_amap_mcp_server_accepts_official_client_call() -> None:
    settings = Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
    )
    server = create_amap_mcp_server(
        settings,
        provider=MockMapProvider(),
    )
    asgi_app = server.streamable_http_app(
        json_response=True,
        stateless_http=True,
        host="127.0.0.1",
    )
    port = _free_port()
    config = uvicorn.Config(
        asgi_app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        lifespan="on",
    )
    running = uvicorn.Server(config)
    task = asyncio.create_task(running.serve())
    try:
        await _wait_until_started(running)
        client = OfficialMcpClient()
        result = await client.call_tool(
            endpoint=f"http://127.0.0.1:{port}/mcp",
            tool_name="search_places",
            payload={
                "keyword": "洪崖洞",
                "city": "重庆",
                "limit": 1,
            },
            timeout_seconds=10,
        )
        assert result.structured_content is not None
        assert result.structured_content["results"][0]["name"] == "洪崖洞民俗风貌区"
    finally:
        running.should_exit = True
        with suppress(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=10)


async def test_skill_runtime_calls_amap_through_real_mcp_gateway(
    api_client,
) -> None:
    registration = await register_user(api_client)
    owner_id = UUID(str(registration["user"]["id"]))
    port = _free_port()
    settings = Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        mcp_gateway_enabled=True,
        mcp_allowed_connectors="amap",
        mcp_amap_endpoint=f"http://127.0.0.1:{port}/mcp",
    )
    server = create_amap_mcp_server(
        settings,
        provider=MockMapProvider(),
    )
    asgi_app = server.streamable_http_app(
        json_response=True,
        stateless_http=True,
        host="127.0.0.1",
    )
    running = uvicorn.Server(
        uvicorn.Config(
            asgi_app,
            host="127.0.0.1",
            port=port,
            log_level="error",
            lifespan="on",
        )
    )
    task = asyncio.create_task(running.serve())
    try:
        await _wait_until_started(running)
        service = McpConnectorService(app.state.test_session, settings)
        await service.set_enabled(
            connector_id="amap",
            enabled=True,
            actor_id=owner_id,
            reason="real MCP protocol test",
        )
        runtime = await build_skill_runtime(
            session=app.state.test_session,
            settings=settings,
            owner_id=owner_id,
        )

        result = await runtime.execute(
            "destination-research",
            {
                "query": "洪崖洞",
                "city": "重庆",
                "limit": 1,
            },
        )

        assert result.output.places[0].name == "洪崖洞民俗风貌区"
        assert runtime.tool_context.runner.audits[0].provider == "mcp:amap"
    finally:
        running.should_exit = True
        with suppress(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=10)


class StaticWeatherProvider:
    name = "static-weather"

    async def forecast(self, *, city: str, date: Date) -> WeatherSnapshot:
        return WeatherSnapshot(
            provider=self.name,
            city=city,
            date=date,
            condition="晴",
            temperature_max_c=24,
            temperature_min_c=15,
            precipitation_probability=10,
            freshness="live",
            evidence=EvidenceDraft(
                fact_type="weather",
                provider=self.name,
                provider_record_id=f"weather:{city}:{date.isoformat()}",
                fetched_at=datetime.now(UTC),
                confidence=0.9,
                freshness="live",
                value={},
            ),
        )


async def test_weather_skill_writes_evidence_from_real_mcp_result(
    api_client,
) -> None:
    registration = await register_user(api_client)
    owner_id = UUID(str(registration["user"]["id"]))
    port = _free_port()
    settings = Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        mcp_gateway_enabled=True,
        mcp_allowed_connectors="weather",
        mcp_weather_endpoint=f"http://127.0.0.1:{port}/mcp",
    )
    server = create_weather_mcp_server(
        settings,
        provider=StaticWeatherProvider(),
    )
    asgi_app = server.streamable_http_app(
        json_response=True,
        stateless_http=True,
        host="127.0.0.1",
    )
    running = uvicorn.Server(
        uvicorn.Config(
            asgi_app,
            host="127.0.0.1",
            port=port,
            log_level="error",
            lifespan="on",
        )
    )
    task = asyncio.create_task(running.serve())
    try:
        await _wait_until_started(running)
        service = McpConnectorService(app.state.test_session, settings)
        await service.set_enabled(
            connector_id="weather",
            enabled=True,
            actor_id=owner_id,
            reason="real weather MCP protocol test",
        )
        runtime = await build_skill_runtime(
            session=app.state.test_session,
            settings=settings,
            owner_id=owner_id,
        )

        result = await runtime.execute(
            "weather-and-clothing",
            {"city": "重庆", "date": "2026-12-01"},
        )

        assert result.output.evidence_ids
        assert runtime.tool_context.runner.audits[0].provider == "mcp:weather"
        evidence = await EvidenceRepository(
            app.state.test_session
        ).get_for_owner(
            owner_id=owner_id,
            evidence_id=UUID(str(result.output.evidence_ids[0])),
        )
        assert evidence is not None
        assert evidence.provider == "mcp:weather"
    finally:
        running.should_exit = True
        with suppress(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=10)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_until_started(server: uvicorn.Server) -> None:
    for _ in range(100):
        if server.started:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("MCP server did not start")
