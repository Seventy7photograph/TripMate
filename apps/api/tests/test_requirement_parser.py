# 文件说明：后端自动化测试：test_requirement_parser。
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

from app.main import app
from app.models.agent_run import AgentRun
from tests.test_auth import auth_headers, register_user


async def test_parse_complete_request_into_trip_brief(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(
        api_client,
        email=f"brief-complete-{uuid4().hex}@example.com",
    )
    token = str(registration["access_token"])

    response = await api_client.post(
        "/api/v1/briefs/parse",
        headers=auth_headers(token),
        json={
            "text": (
                "2026年12月1日到12月3日，我和朋友2个人从上海去重庆，"
                "预算5000元，喜欢美食和城市漫步，想轻松一点。"
            )
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["missing_fields"] == []
    assert payload["questions"] == []
    assert payload["brief"] == {
        "destination": "重庆",
        "origin": "上海",
        "start_date": "2026-12-01",
        "end_date": "2026-12-03",
        "party_size": 2,
        "budget_minor": 500_000,
        "currency": "CNY",
        "interests": ["美食", "城市漫步"],
        "pace": "relaxed",
        "transport_preferences": [],
        "lodging_preferences": [],
        "must_visit": [],
        "avoid": [],
        "constraints": [],
    }


async def test_parse_missing_budget_returns_question_without_inventing(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(
        api_client,
        email=f"brief-budget-{uuid4().hex}@example.com",
    )
    token = str(registration["access_token"])

    response = await api_client.post(
        "/api/v1/briefs/parse",
        headers=auth_headers(token),
        json={
            "text": (
                "2026年12月1日到12月3日，2个人从上海去重庆，"
                "喜欢美食和城市漫步。"
            )
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["brief"] is None
    assert payload["missing_fields"] == ["budget_minor"]
    assert payload["draft"]["destination"] == "重庆"
    assert payload["draft"]["origin"] == "上海"
    assert payload["draft"]["start_date"] == "2026-12-01"
    assert payload["draft"]["party_size"] == 2
    assert len(payload["questions"]) == 1
    assert "预算" in payload["questions"][0]


async def test_parse_ambiguous_date_returns_questions_without_guessing_year(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(
        api_client,
        email=f"brief-date-{uuid4().hex}@example.com",
    )
    token = str(registration["access_token"])

    response = await api_client.post(
        "/api/v1/briefs/parse",
        headers=auth_headers(token),
        json={"text": "10月去重庆，2个人，预算5000元，喜欢美食。"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["brief"] is None
    assert payload["missing_fields"] == ["start_date", "end_date"]
    assert len(payload["questions"]) == 1
    assert "日期" in payload["questions"][0]


async def test_parse_requires_authentication(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/briefs/parse",
        json={"text": "2026年12月1日到12月3日，2个人去重庆，预算5000元。"},
    )

    assert response.status_code == 401


async def test_parse_persists_model_usage_without_a_trip(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    user_id = UUID(str(registration["user"]["id"]))

    response = await api_client.post(
        "/api/v1/briefs/parse",
        headers=auth_headers(token),
        json={
            "text": (
                "2026年12月1日到12月3日，2个人从上海去重庆，"
                "预算5000元，喜欢美食。"
            )
        },
    )

    assert response.status_code == 200, response.text
    run = await app.state.test_session.scalar(
        select(AgentRun).where(AgentRun.created_by == user_id)
    )
    assert run is not None
    assert run.trip_id is None
    assert run.purpose == "brief_parse"
    assert run.provider == "mock"
    assert run.model_name == "mock-tripbrief-v1"
    assert run.input_tokens > 0
    assert run.output_tokens > 0
    assert run.latency_ms > 0
    assert run.prompt_versions == [
        {
            "agent": "requirement-parser",
            "prompt_id": "system",
            "version": "1.0.0",
            "sha256": run.prompt_versions[0]["sha256"],
        }
    ]
    assert run.result == response.json()
