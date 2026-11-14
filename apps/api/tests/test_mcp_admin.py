# 文件说明：MCP connector 管理员接口测试。

from uuid import uuid4

import httpx

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
