# 文件说明：Agent Skill 管理可观测性测试。

from uuid import uuid4

import httpx

from app.main import app
from app.models.agent_run import AgentRun
from app.models.tool_call_log import ToolCallLog
from tests.test_admin_permissions import promote_admin
from tests.test_auth import auth_headers, register_user


async def test_costs_and_tool_health_expose_skill_runtime_metrics(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await register_user(
        api_client,
        email=f"skill-observability-{uuid4().hex}@example.com",
    )
    await promote_admin(str(admin["user"]["id"]))
    token = str(admin["access_token"])
    owner_id = admin["user"]["id"]

    first = AgentRun(
        created_by=owner_id,
        trip_id=None,
        status="completed",
        progress=100,
        purpose="planning",
        provider="deepseek",
        model_name="deepseek-flash",
        input_tokens=100,
        output_tokens=50,
        latency_ms=900,
        estimated_cost_minor=120,
        tool_call_count=1,
        skills_used=[
            {
                "name": "destination-research",
                "version": "1.0.0",
                "status": "completed",
            },
            {
                "name": "route-optimization",
                "version": "1.0.0",
                "status": "completed",
            },
        ],
        skill_route={
            "confidence": 0.93,
            "fallback_reason": None,
        },
        events=[],
    )
    second = AgentRun(
        created_by=owner_id,
        trip_id=None,
        status="failed",
        progress=100,
        purpose="planning",
        provider="deepseek",
        model_name="deepseek-flash",
        input_tokens=20,
        output_tokens=10,
        latency_ms=300,
        estimated_cost_minor=30,
        tool_call_count=1,
        skills_used=[
            {
                "name": "route-optimization",
                "version": "1.0.0",
                "status": "failed",
            }
        ],
        skill_route={
            "confidence": 0.72,
            "fallback_reason": "router unavailable",
        },
        events=[],
    )
    app.state.test_session.add_all([first, second])
    await app.state.test_session.flush()
    app.state.test_session.add_all(
        [
            ToolCallLog(
                agent_run_id=first.id,
                tool_name="search_places",
                provider="amap",
                input_hash="a" * 64,
                status="success",
                latency_ms=180,
                estimated_cost_minor=0,
            ),
            ToolCallLog(
                agent_run_id=second.id,
                tool_name="search_places",
                provider="amap",
                input_hash="b" * 64,
                status="error",
                latency_ms=420,
                estimated_cost_minor=0,
                error_code="provider_timeout",
            ),
        ]
    )
    await app.state.test_session.commit()

    costs = await api_client.get(
        "/api/v1/admin/costs?days=7",
        headers=auth_headers(token),
    )
    assert costs.status_code == 200, costs.text
    by_skill = {item["key"]: item for item in costs.json()["by_skill"]}
    assert by_skill["route-optimization"]["runs"] == 2
    assert by_skill["route-optimization"]["failed_runs"] == 1
    assert by_skill["destination-research"]["cost_minor"] == 60

    tools = await api_client.get(
        "/api/v1/admin/tool-health?hours=24",
        headers=auth_headers(token),
    )
    assert tools.status_code == 200, tools.text
    item = tools.json()["items"][0]
    assert item["tool_name"] == "search_places"
    assert item["provider"] == "amap"
    assert item["invocations"] == 2
    assert item["failed_invocations"] == 1
    assert item["status"] == "degraded"
    assert item["last_error_code"] == "provider_timeout"

    runs = await api_client.get(
        "/api/v1/admin/agent-runs",
        headers=auth_headers(token),
    )
    assert runs.status_code == 200
    payload = runs.json()["items"][0]
    assert payload["skills_used"]
    assert payload["skill_route"]["confidence"] >= 0.7
