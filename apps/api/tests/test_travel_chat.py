# 文件说明：后端自动化测试：test_travel_chat。
import httpx
from sqlalchemy import select

from app.main import app
from app.models.agent_run import AgentRun
from tests.test_auth import auth_headers, register_user


async def test_travel_chat_returns_planning_brief(api_client: httpx.AsyncClient) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={
            "message": "2026年12月1日到12月3日，2个人从上海去重庆，预算5000元。",
            "history": [],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "plan_trip"
    assert payload["requires_planning"] is True
    assert payload["brief"]["destination"] == "重庆"

    run = await app.state.test_session.scalar(
        select(AgentRun)
        .where(AgentRun.purpose == "travel_chat")
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    assert run is not None
    assert run.status == "completed"
    assert run.skill_route["intent"] == "plan_trip"


async def test_travel_chat_answers_destination_question(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={"message": "泉州开元寺有什么值得看的？", "history": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "destination_research"
    assert payload["in_scope"] is True
    assert payload["answer"]
    assert "search_places" in payload["used_tools"]


async def test_travel_chat_rejects_non_travel_request(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={"message": "帮我写一段 Python 快速排序代码", "history": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "out_of_scope"
    assert payload["in_scope"] is False
    assert payload["requires_planning"] is False


async def test_travel_chat_rejects_empty_request(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={"message": "", "history": []},
    )

    assert response.status_code == 422
