# 文件说明：后端自动化测试：test_fake_planner。
import json
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest

from app.agents.fake_planner import FakePlanner
from app.schemas.ai import TripBriefContract

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def brief_fixture() -> TripBriefContract:
    payload = json.loads(
        (FIXTURES / "trip_briefs/chongqing-full.json").read_text(encoding="utf-8")
    )
    return TripBriefContract.model_validate(payload)


def test_fake_planner_is_deterministic_and_uses_shared_contracts() -> None:
    planner = FakePlanner()
    brief = brief_fixture()
    trip_id = str(uuid4())

    first = planner.plan(trip_id=trip_id, version=3, brief=brief)
    second = planner.plan(trip_id=trip_id, version=3, brief=brief)

    assert first == second
    assert first.trip_id == trip_id
    assert first.version == 3
    assert len(first.days) == 3
    assert first.days[0].date.isoformat() == "2026-12-01"
    assert first.days[0].stops[0].source.freshness == "mock"
    assert first.days[0].stops[0].source.provider == "mock"
    assert first.validation_summary == []
    assert "洪崖洞" in {
        stop.place_name for day in first.days for stop in day.stops
    }


async def test_planning_job_persists_events_result_and_tool_log(
    api_client: httpx.AsyncClient,
) -> None:
    from sqlalchemy import select

    from app.main import app
    from app.models.agent_run import AgentRun
    from app.models.tool_call_log import ToolCallLog
    from tests.test_auth import auth_headers, register_user
    from tests.test_trips_crud import trip_payload

    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip_response = await api_client.post(
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
    trip = trip_response.json()

    start = await api_client.post(
        f"/api/v1/trips/{trip['id']}/plan",
        headers=auth_headers(token),
        json={"expected_version": 1},
    )
    assert start.status_code == 202, start.text
    job_id = start.json()["job_id"]

    poll = await api_client.get(
        f"/api/v1/jobs/{job_id}",
        headers=auth_headers(token),
    )
    assert poll.status_code == 200, poll.text
    job = poll.json()
    assert job["status"] == "completed"
    assert job["result"]["trip_id"] == trip["id"]
    assert len(job["result"]["days"]) == 3
    event_types = [event["type"] for event in job["events"]]
    assert event_types[0] == "stage"
    assert event_types.count("tool_call") >= 3
    assert "validation" in event_types
    assert event_types[-1] == "complete"

    session = app.state.test_session
    run = await session.scalar(
        select(AgentRun).where(AgentRun.id == UUID(job_id))
    )
    tool_calls = list(
        (
            await session.execute(
                select(ToolCallLog).where(ToolCallLog.agent_run_id == UUID(job_id))
            )
        ).scalars()
    )
    assert run is not None
    assert run.status == "completed"
    assert run.model_name == "mock-langgraph-composer"
    assert run.tool_call_count >= 3
    assert tool_calls
    assert tool_calls[0].status == "success"
    assert "api_key" not in poll.text.lower()


async def test_planning_sse_replays_ordered_events(
    api_client: httpx.AsyncClient,
) -> None:
    from tests.test_auth import auth_headers, register_user
    from tests.test_trips_crud import trip_payload

    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(destination="重庆"),
        )
    ).json()
    start = await api_client.post(
        f"/api/v1/trips/{trip['id']}/plan",
        headers=auth_headers(token),
        json={"expected_version": 1},
    )
    job_id = start.json()["job_id"]

    async with api_client.stream(
        "GET",
        f"/api/v1/jobs/{job_id}/events",
        headers=auth_headers(token),
    ) as response:
        body = "".join([chunk async for chunk in response.aiter_text()])

    assert response.status_code == 200
    assert body.index("event: stage") < body.index("event: complete")
    assert '"status":"completed"' in body


async def test_failed_planner_records_error_event(
    api_client: httpx.AsyncClient,
) -> None:
    from app.api.v1.planning import get_planning_service
    from app.core.config import get_settings
    from app.main import app
    from app.services.planning_service import PlanningService
    from tests.test_auth import auth_headers, register_user
    from tests.test_trips_crud import trip_payload

    class FailingGraph:
        provider_name = "test"
        model_name = "failing-graph"

        async def run(self, **_: object):
            raise RuntimeError("fake planning failure")

    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(destination="重庆"),
        )
    ).json()

    async def failing_service():
        return PlanningService(
            app.state.test_session,
            get_settings(),
            graph=FailingGraph(),  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_planning_service] = failing_service
    try:
        start = await api_client.post(
            f"/api/v1/trips/{trip['id']}/plan",
            headers=auth_headers(token),
            json={"expected_version": 1},
        )
    finally:
        app.dependency_overrides.pop(get_planning_service, None)

    assert start.status_code == 202
    job = await api_client.get(
        f"/api/v1/jobs/{start.json()['job_id']}",
        headers=auth_headers(token),
    )
    assert job.json()["status"] == "failed"
    assert job.json()["events"][-1]["type"] == "error"
    assert job.json()["error_code"] == "planning_failed"


async def test_planning_jobs_are_owner_isolated(
    api_client: httpx.AsyncClient,
) -> None:
    from tests.test_auth import auth_headers, register_user
    from tests.test_trips_crud import trip_payload

    owner = await register_user(
        api_client,
        email=f"plan-owner-{uuid4().hex}@example.com",
    )
    outsider = await register_user(
        api_client,
        email=f"plan-outsider-{uuid4().hex}@example.com",
    )
    owner_token = str(owner["access_token"])
    outsider_token = str(outsider["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(owner_token),
            json=trip_payload(),
        )
    ).json()
    start = await api_client.post(
        f"/api/v1/trips/{trip['id']}/plan",
        headers=auth_headers(owner_token),
        json={"expected_version": 1},
    )
    job_id = start.json()["job_id"]

    poll = await api_client.get(
        f"/api/v1/jobs/{job_id}",
        headers=auth_headers(outsider_token),
    )
    assert poll.status_code == 404


@pytest.mark.parametrize("key_name", ["LLM_API_KEY", "OPENAI_API_KEY"])
async def test_mock_planning_needs_no_model_key(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    key_name: str,
) -> None:
    from tests.test_auth import auth_headers, register_user
    from tests.test_trips_crud import trip_payload

    monkeypatch.delenv(key_name, raising=False)
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(),
        )
    ).json()
    response = await api_client.post(
        f"/api/v1/trips/{trip['id']}/plan",
        headers=auth_headers(token),
        json={"expected_version": 1},
    )
    assert response.status_code == 202
