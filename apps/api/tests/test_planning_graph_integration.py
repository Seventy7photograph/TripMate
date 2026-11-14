# 文件说明：后端自动化测试：test_planning_graph_integration。
from uuid import UUID

import httpx
from pydantic import SecretStr
from sqlalchemy import select

from app.api.deps import get_settings
from app.core.config import Settings
from app.main import app
from app.models.agent_run import AgentRun
from app.models.tool_call_log import ToolCallLog
from app.services.feature_service import FeatureFlagService
from app.services.planning_service import PlanningService
from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


async def test_planning_service_persists_langgraph_result_and_audits(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(
                destination="重庆",
                start_date="2026-12-01",
                end_date="2026-12-03",
                budget_minor=500_000,
                must_visit=["洪崖洞"],
            ),
        )
    ).json()

    started = await api_client.post(
        f"/api/v1/trips/{trip['id']}/plan",
        headers=auth_headers(token),
        json={"expected_version": 1},
    )
    assert started.status_code == 202, started.text

    job = (
        await api_client.get(
            f"/api/v1/jobs/{started.json()['job_id']}",
            headers=auth_headers(token),
        )
    ).json()
    assert job["status"] == "completed"
    assert job["result"]["days"]
    assert {
        stop["source"]["provider"]
        for day in job["result"]["days"]
        for stop in day["stops"]
    } == {"mock"}
    event_types = [event["type"] for event in job["events"]]
    assert event_types.count("tool_call") >= 3
    assert "validation" in event_types
    assert event_types[-1] == "complete"
    assert [event["sequence"] for event in job["events"]] == list(
        range(1, len(job["events"]) + 1)
    )
    assert job["tool_call_count"] >= 3
    assert job["loop_count"] == 0

    run = await app.state.test_session.scalar(
        select(AgentRun).where(AgentRun.id == UUID(job["id"]))
    )
    assert run is not None
    assert run.status == "completed"
    assert run.provider == "mock"
    assert run.model_name == "mock-langgraph-composer"
    assert run.tool_call_count == job["tool_call_count"]
    assert run.skills_used == []
    assert run.skill_route is not None
    assert run.skill_route["intent"] == "create_trip_plan"
    assert "route-optimization" in run.skill_route["selected_skills"]
    assert "destination-research" in run.skill_route["selected_skills"]
    assert run.skill_route["fallback_reason"] is None

    tool_calls = list(
        (
            await app.state.test_session.execute(
                select(ToolCallLog).where(ToolCallLog.agent_run_id == UUID(job["id"]))
            )
        ).scalars()
    )
    assert {item.tool_name for item in tool_calls} >= {
        "search_places",
        "get_route",
        "calculate_budget",
    }
    assert all(item.status == "success" for item in tool_calls)


async def test_planning_returns_service_unavailable_when_live_llm_is_missing(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(destination="重庆"),
        )
    ).json()

    def live_settings() -> Settings:
        return Settings(
            app_env="test",
            provider_profile="live",
            amap_web_service_key=SecretStr("test-amap-key"),
            llm_api_key=None,
            llm_model="",
        )

    app.dependency_overrides[get_settings] = live_settings
    try:
        response = await api_client.post(
            f"/api/v1/trips/{trip['id']}/plan",
            headers=auth_headers(token),
            json={"expected_version": 1},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "llm_not_configured"


async def test_conversation_plan_can_be_applied_to_itinerary_for_map(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(
                destination="重庆",
                start_date="2026-12-01",
                end_date="2026-12-03",
                must_visit=["洪崖洞"],
            ),
        )
    ).json()

    started = await api_client.post(
        f"/api/v1/trips/{trip['id']}/plan",
        headers=auth_headers(token),
        json={"expected_version": 1, "apply_to_itinerary": True},
    )
    assert started.status_code == 202, started.text
    job = (
        await api_client.get(
            f"/api/v1/jobs/{started.json()['job_id']}",
            headers=auth_headers(token),
        )
    ).json()
    assert job["status"] == "completed"

    itinerary = await api_client.get(
        f"/api/v1/trips/{trip['id']}/itinerary",
        headers=auth_headers(token),
    )
    assert itinerary.status_code == 200
    days = itinerary.json()["days"]
    assert len(days) == 3
    assert days[0]["stops"]
    assert days[0]["stops"][0]["location"] is not None

    map_response = await api_client.get(
        (
            f"/api/v1/trips/{trip['id']}/days/{days[0]['id']}/map"
            f"?expected_version={itinerary.json()['version']}&include_route=false"
        ),
        headers=auth_headers(token),
    )
    assert map_response.status_code == 200
    assert map_response.headers["content-type"].startswith("image/")


async def test_planning_job_is_queued_then_executed_by_worker(
    api_client: httpx.AsyncClient,
) -> None:
    class RecordingQueue:
        is_inline = False

        def __init__(self) -> None:
            self.job_ids = []

        async def enqueue(self, job_id):
            self.job_ids.append(job_id)

    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(destination="重庆"),
        )
    ).json()
    queue = RecordingQueue()
    service = PlanningService(
        app.state.test_session,
        get_settings(),
        queue=queue,
    )

    started = await service.start(
        owner_id=UUID(str(registration["user"]["id"])),
        trip_id=UUID(str(trip["id"])),
        expected_version=1,
    )

    assert started.status == "queued"
    assert queue.job_ids == [started.id]

    completed = await service.run_job(started.id)
    assert completed.status == "completed"


async def test_disabling_agent_skills_falls_back_without_router(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    owner_id = UUID(str(registration["user"]["id"]))
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(destination="重庆"),
        )
    ).json()
    await FeatureFlagService(app.state.test_session).toggle(
        key="agent_skills_enabled",
        enabled=False,
        actor_id=owner_id,
        reason="rollback test",
    )

    started = await api_client.post(
        f"/api/v1/trips/{trip['id']}/plan",
        headers=auth_headers(token),
        json={"expected_version": 1},
    )
    assert started.status_code == 202, started.text
    job = (
        await api_client.get(
            f"/api/v1/jobs/{started.json()['job_id']}",
            headers=auth_headers(token),
        )
    ).json()

    assert job["status"] == "completed"
    run = await app.state.test_session.scalar(
        select(AgentRun).where(AgentRun.id == UUID(job["id"]))
    )
    assert run is not None
    assert run.skill_route["fallback_reason"] == "agent_skills_disabled"
    assert run.skill_route["selected_skills"] == []
