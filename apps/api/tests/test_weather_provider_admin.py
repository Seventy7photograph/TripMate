# 文件说明：Admin Weather Provider 配置与开关测试。

from uuid import uuid4

import httpx

from tests.test_admin_permissions import promote_admin
from tests.test_auth import auth_headers, register_user


async def test_admin_can_view_and_toggle_weather_provider(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await register_user(
        api_client,
        email=f"weather-provider-{uuid4().hex}@example.com",
    )
    await promote_admin(str(admin["user"]["id"]))
    token = str(admin["access_token"])

    providers = await api_client.get(
        "/api/v1/admin/providers",
        headers=auth_headers(token),
    )

    assert providers.status_code == 200, providers.text
    weather = next(
        item for item in providers.json()["items"]
        if item["key"] == "weather_provider"
    )
    assert weather["provider_name"] == "open-meteo"
    assert weather["enabled"] is True
    assert weather["configured"] is True
    assert weather["configuration"]["fallback_enabled"] is True
    assert weather["configuration"]["forecast_endpoint"].startswith(
        "https://"
    )

    disabled = await api_client.post(
        "/api/v1/admin/features/weather_provider/toggle",
        headers=auth_headers(token),
        json={"enabled": False, "reason": "weather rollback"},
    )

    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["enabled"] is False
