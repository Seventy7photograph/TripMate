# 文件说明：后端自动化测试：test_admin_permissions。
from uuid import uuid4

import httpx
from sqlalchemy import update

from app.api.deps import get_settings
from app.core.config import Settings
from app.main import app
from app.models.agent_run import AgentRun
from app.models.user import User as UserModel
from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


async def promote_admin(user_id: str) -> None:
    await app.state.test_session.execute(
        update(UserModel)
        .where(UserModel.id == user_id)
        .values(role="admin")
    )
    await app.state.test_session.commit()


async def test_admin_endpoints_require_admin_role(api_client: httpx.AsyncClient) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    forbidden = await api_client.get(
        "/api/v1/admin/agent-runs",
        headers=auth_headers(token),
    )

    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "admin_required"


async def test_admin_can_view_agent_runs_costs_and_providers(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await register_user(
        api_client,
        email=f"admin-{uuid4().hex}@example.com",
    )
    await promote_admin(str(admin["user"]["id"]))
    token = str(admin["access_token"])

    me = await api_client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["role"] == "admin"

    app.state.test_session.add_all(
        [
            AgentRun(
                created_by=admin["user"]["id"],
                trip_id=None,
                status="completed",
                progress=100,
                purpose="planning",
                provider="deepseek",
                model_name="deepseek-chat",
                input_tokens=100,
                output_tokens=50,
                latency_ms=1_200,
                estimated_cost_minor=120,
                events=[],
            ),
            AgentRun(
                created_by=admin["user"]["id"],
                trip_id=None,
                status="failed",
                progress=100,
                purpose="brief_parse",
                provider="deepseek",
                model_name="deepseek-chat",
                input_tokens=20,
                output_tokens=10,
                latency_ms=300,
                estimated_cost_minor=30,
                error_code="invalid_llm_output",
                error_message="Requirement parsing failed",
                events=[],
            ),
            AgentRun(
                created_by=admin["user"]["id"],
                trip_id=None,
                status="completed",
                progress=100,
                purpose="planning",
                provider="mock",
                model_name="mock-langgraph-composer",
                input_tokens=1_000,
                output_tokens=1_000,
                latency_ms=1,
                estimated_cost_minor=9_999,
                events=[],
            ),
        ]
    )
    await app.state.test_session.commit()

    runs = await api_client.get(
        "/api/v1/admin/agent-runs",
        headers=auth_headers(token),
    )
    assert runs.status_code == 200, runs.text
    assert runs.json()["total"] == 2
    assert len(runs.json()["items"]) == 2
    assert "result" not in runs.json()["items"][0]

    costs = await api_client.get(
        "/api/v1/admin/costs?days=7",
        headers=auth_headers(token),
    )
    assert costs.status_code == 200, costs.text
    assert costs.json()["total_runs"] == 2
    assert costs.json()["total_input_tokens"] == 120
    assert costs.json()["total_output_tokens"] == 60
    assert costs.json()["total_cost_minor"] == 150
    assert costs.json()["failed_runs"] == 1
    assert costs.json()["limits"]["user_daily_cost_minor"] > 0

    providers = await api_client.get(
        "/api/v1/admin/providers",
        headers=auth_headers(token),
    )
    assert providers.status_code == 200, providers.text
    assert {item["key"] for item in providers.json()["items"]} == {
        "llm_provider",
        "map_provider",
        "weather_provider",
    }
    assert "test-secret-key" not in providers.text


async def test_feature_toggle_blocks_ai_and_map_and_writes_audit(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await register_user(
        api_client,
        email=f"admin-toggle-{uuid4().hex}@example.com",
    )
    await promote_admin(str(admin["user"]["id"]))
    admin_token = str(admin["access_token"])

    user = await register_user(
        api_client,
        email=f"toggle-user-{uuid4().hex}@example.com",
    )
    user_token = str(user["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(user_token),
            json=trip_payload(destination="重庆"),
        )
    ).json()

    disabled = await api_client.post(
        "/api/v1/admin/features/ai_planning/toggle",
        headers=auth_headers(admin_token),
        json={"enabled": False, "reason": "maintenance"},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["enabled"] is False

    planning = await api_client.post(
        f"/api/v1/trips/{trip['id']}/plan",
        headers=auth_headers(user_token),
        json={"expected_version": 1},
    )
    assert planning.status_code == 503
    assert planning.json()["detail"]["code"] == "feature_disabled"

    map_toggle = await api_client.post(
        "/api/v1/admin/features/map_provider/toggle",
        headers=auth_headers(admin_token),
        json={"enabled": False},
    )
    assert map_toggle.status_code == 200
    places = await api_client.get(
        "/api/v1/places/search?q=洪崖洞&city=重庆",
        headers=auth_headers(user_token),
    )
    assert places.status_code == 503
    assert places.json()["detail"]["feature"] == "map_provider"

    llm_toggle = await api_client.post(
        "/api/v1/admin/features/llm_provider/toggle",
        headers=auth_headers(admin_token),
        json={"enabled": False},
    )
    assert llm_toggle.status_code == 200
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="test",
        provider_profile="live",
        map_provider_profile="mock",
    )
    try:
        parsed = await api_client.post(
            "/api/v1/briefs/parse",
            headers=auth_headers(user_token),
            json={"text": "2026年12月1日到12月3日，2个人去重庆，预算5000元。"},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert parsed.status_code == 503
    assert parsed.json()["detail"]["feature"] == "llm_provider"

    features = await api_client.get(
        "/api/v1/admin/features",
        headers=auth_headers(admin_token),
    )
    assert features.status_code == 200
    assert {
        item["key"]: item["enabled"] for item in features.json()["items"]
    }["ai_planning"] is False

    audits = await api_client.get(
        "/api/v1/admin/audit-logs",
        headers=auth_headers(admin_token),
    )
    assert audits.status_code == 200
    assert audits.json()["total"] >= 3
    assert audits.json()["items"][0]["action"] == "feature.toggle"
