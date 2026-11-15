# 文件说明：MCP connector 管理员接口测试。

import asyncio
import socket
from contextlib import suppress
from uuid import uuid4

import httpx
import uvicorn

from app.api.deps import get_settings
from app.core.config import Settings
from app.main import app
from app.mcp.server import create_amap_mcp_server
from app.providers.mock_map import MockMapProvider
from tests.test_admin_permissions import promote_admin
from tests.test_auth import auth_headers, register_user


async def _admin_token(api_client: httpx.AsyncClient) -> str:
    admin = await register_user(
        api_client,
        email=f"mcp-admin-{uuid4().hex}@example.com",
    )
    await promote_admin(str(admin["user"]["id"]))
    return str(admin["access_token"])


async def test_admin_can_list_and_toggle_mcp_connectors(
    api_client: httpx.AsyncClient,
) -> None:
    token = await _admin_token(api_client)

    listed = await api_client.get(
        "/api/v1/admin/mcp-connectors",
        headers=auth_headers(token),
    )

    assert listed.status_code == 200, listed.text
    items = {item["connector_id"]: item for item in listed.json()["items"]}
    assert set(items) == {"amap", "weather"}
    assert items["amap"]["enabled"] is False
    assert items["amap"]["status"] == "disabled"
    assert items["amap"]["daily_quota"] > 0
    assert items["amap"]["rate_limit_per_minute"] > 0

    enabled = await api_client.post(
        "/api/v1/admin/mcp-connectors/weather/toggle",
        headers=auth_headers(token),
        json={"enabled": True, "reason": "weather connector rollout"},
    )

    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["enabled"] is True
    assert enabled.json()["status"] == "configured"

    audits = await api_client.get(
        "/api/v1/admin/audit-logs",
        headers=auth_headers(token),
    )
    assert audits.status_code == 200
    assert any(
        item["action"] == "mcp_connector.toggle"
        and item["target_id"] == "weather"
        for item in audits.json()["items"]
    )


async def test_mcp_connector_toggle_requires_admin(
    api_client: httpx.AsyncClient,
) -> None:
    user = await register_user(
        api_client,
        email=f"mcp-user-{uuid4().hex}@example.com",
    )

    response = await api_client.post(
        "/api/v1/admin/mcp-connectors/amap/toggle",
        headers=auth_headers(str(user["access_token"])),
        json={"enabled": True},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "admin_required"


async def test_admin_can_run_real_mcp_health_check(
    api_client: httpx.AsyncClient,
) -> None:
    token = await _admin_token(api_client)
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
    running = uvicorn.Server(
        uvicorn.Config(
            server.streamable_http_app(
                json_response=True,
                stateless_http=True,
                host="127.0.0.1",
            ),
            host="127.0.0.1",
            port=port,
            log_level="error",
            lifespan="on",
        )
    )
    task = asyncio.create_task(running.serve())
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        await _wait_until_started(running)
        response = await api_client.post(
            "/api/v1/admin/mcp-connectors/amap/check",
            headers=auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)
        running.should_exit = True
        with suppress(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=10)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["configured"] is True
    assert payload["latency_ms"] >= 1
    assert payload["checked_at"] is not None


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
