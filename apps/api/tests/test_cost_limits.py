# 文件说明：后端自动化测试：test_cost_limits。
import httpx
import pytest

from app.api.deps import get_settings
from app.core.config import Settings
from app.main import app
from app.models.agent_run import AgentRun
from app.services.cost_guard import (
    CostGuard,
    CostLimitExceeded,
    hash_client_ip,
    settled_cost_minor,
)
from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


async def create_trip_for_user(
    api_client: httpx.AsyncClient,
) -> tuple[dict[str, object], dict[str, object]]:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(destination="重庆"),
        )
    ).json()
    return registration, trip


async def test_user_daily_cost_limit_blocks_new_planning_run(
    api_client: httpx.AsyncClient,
) -> None:
    registration, trip = await create_trip_for_user(api_client)
    token = str(registration["access_token"])
    settings = Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        daily_user_cost_limit_minor=1,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.test_session.add(
        AgentRun(
            created_by=registration["user"]["id"],
            trip_id=None,
            status="completed",
            progress=100,
            purpose="planning",
            provider="mock",
            model_name="mock-langgraph-composer",
            estimated_cost_minor=10,
            events=[],
        )
    )
    await app.state.test_session.commit()
    try:
        response = await api_client.post(
            f"/api/v1/trips/{trip['id']}/plan",
            headers=auth_headers(token),
            json={"expected_version": 1},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "cost_limit_exceeded"
    assert response.json()["detail"]["scope"] == "user"


async def test_ip_daily_cost_limit_uses_hashed_client_address(
    api_client: httpx.AsyncClient,
) -> None:
    registration, trip = await create_trip_for_user(api_client)
    token = str(registration["access_token"])
    settings = Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        daily_user_cost_limit_minor=1_000_000,
        daily_ip_cost_limit_minor=1,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.test_session.add(
        AgentRun(
            created_by=registration["user"]["id"],
            trip_id=None,
            status="completed",
            progress=100,
            purpose="planning",
            provider="mock",
            model_name="mock-langgraph-composer",
            request_ip_hash=hash_client_ip(
                "127.0.0.1",
                settings.jwt_secret.get_secret_value(),
            ),
            estimated_cost_minor=10,
            events=[],
        )
    )
    await app.state.test_session.commit()
    try:
        response = await api_client.post(
            f"/api/v1/trips/{trip['id']}/plan",
            headers=auth_headers(token),
            json={"expected_version": 1},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 429
    assert response.json()["detail"]["scope"] == "ip"
    assert response.json()["detail"]["code"] == "cost_limit_exceeded"


async def test_provider_daily_cost_limit_blocks_new_planning_run(
    api_client: httpx.AsyncClient,
) -> None:
    registration, trip = await create_trip_for_user(api_client)
    token = str(registration["access_token"])
    settings = Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        daily_user_cost_limit_minor=1_000_000,
        daily_ip_cost_limit_minor=1_000_000,
        daily_provider_cost_limit_minor=1,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.test_session.add(
        AgentRun(
            created_by=registration["user"]["id"],
            trip_id=None,
            status="completed",
            progress=100,
            purpose="planning",
            provider="mock",
            model_name="mock-langgraph-composer",
            estimated_cost_minor=10,
            events=[],
        )
    )
    await app.state.test_session.commit()
    try:
        response = await api_client.post(
            f"/api/v1/trips/{trip['id']}/plan",
            headers=auth_headers(token),
            json={"expected_version": 1},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 429
    assert response.json()["detail"]["scope"] == "provider"


async def test_cost_guard_counts_requested_reservation_before_execution(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    owner_id = registration["user"]["id"]
    settings = Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        daily_user_cost_limit_minor=1_005,
        daily_ip_cost_limit_minor=1_000_000,
        daily_provider_cost_limit_minor=1_000_000,
    )
    app.state.test_session.add(
        AgentRun(
            created_by=owner_id,
            trip_id=None,
            status="completed",
            progress=100,
            purpose="planning",
            provider="mock",
            model_name="mock",
            estimated_cost_minor=10,
            events=[],
        )
    )
    await app.state.test_session.flush()

    with pytest.raises(CostLimitExceeded) as exc_info:
        await CostGuard(app.state.test_session, settings).check(
            owner_id=owner_id,
            provider="mock",
            request_ip_hash=None,
            requested_cost_minor=1_000,
        )

    assert exc_info.value.scope == "user"


def test_live_provider_keeps_reservation_when_price_is_unknown() -> None:
    assert settled_cost_minor(
        reserved=1_000,
        reported=0,
        provider="openai_compatible",
    ) == 1_000
    assert settled_cost_minor(
        reserved=1_000,
        reported=0,
        provider="mock",
    ) == 0
