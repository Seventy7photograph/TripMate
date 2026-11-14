# 文件说明：MCP connector 配额与状态服务测试。

from uuid import UUID, uuid4

import httpx
import pytest

from app.core.config import Settings
from app.main import app
from app.services.feature_service import FeatureFlagService
from app.services.mcp_connector_service import (
    McpConnectorService,
    McpQuotaExceededError,
)
from tests.test_auth import register_user


def _settings(*, rate_limit: int, daily_quota: int) -> Settings:
    return Settings(
        app_env="test",
        mcp_rate_limit_per_minute=rate_limit,
        mcp_daily_quota_per_connector=daily_quota,
    )


async def test_connector_rate_limit_and_daily_quota_are_enforced(
    api_client: httpx.AsyncClient,
) -> None:
    session = app.state.test_session
    user = await register_user(
        api_client,
        email=f"mcp-quota-{uuid4().hex}@example.com",
    )
    actor_id = UUID(str(user["user"]["id"]))

    rate_service = McpConnectorService(
        session,
        _settings(rate_limit=2, daily_quota=10),
    )
    await rate_service.set_enabled(
        connector_id="amap",
        enabled=True,
        actor_id=actor_id,
        reason="test",
    )
    await rate_service.authorize_call("amap")
    await rate_service.authorize_call("amap")
    with pytest.raises(McpQuotaExceededError):
        await rate_service.authorize_call("amap")

    quota_service = McpConnectorService(
        session,
        _settings(rate_limit=10, daily_quota=2),
    )
    await quota_service.set_enabled(
        connector_id="weather",
        enabled=True,
        actor_id=actor_id,
        reason="test",
    )
    await quota_service.authorize_call("weather")
    await quota_service.authorize_call("weather")
    with pytest.raises(McpQuotaExceededError):
        await quota_service.authorize_call("weather")


async def test_disabled_connector_is_rejected_before_quota_counting(
    api_client: httpx.AsyncClient,
) -> None:
    service = McpConnectorService(
        app.state.test_session,
        _settings(rate_limit=2, daily_quota=10),
    )

    with pytest.raises(Exception) as exc_info:
        await service.authorize_call("amap")

    assert exc_info.value.__class__.__name__ == "McpNotAllowedError"


async def test_global_mcp_rollout_flag_overrides_enabled_connector(
    api_client: httpx.AsyncClient,
) -> None:
    session = app.state.test_session
    user = await register_user(
        api_client,
        email=f"mcp-rollout-{uuid4().hex}@example.com",
    )
    actor_id = UUID(str(user["user"]["id"]))
    service = McpConnectorService(
        session,
        _settings(rate_limit=10, daily_quota=100),
    )
    await service.set_enabled(
        connector_id="amap",
        enabled=True,
        actor_id=actor_id,
        reason="test",
    )
    await FeatureFlagService(session).toggle(
        key="mcp_gateway_enabled",
        enabled=False,
        actor_id=actor_id,
        reason="rollback",
    )

    assert await service.is_enabled("amap") is False
    with pytest.raises(Exception) as exc_info:
        await service.authorize_call("amap")

    assert exc_info.value.__class__.__name__ == "McpNotAllowedError"
