# 文件说明：后端自动化测试：test_travel_chat。
from datetime import date
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from sqlalchemy import select

from app.api.deps import get_settings
from app.core.config import Settings
from app.main import app
from app.models.agent_run import AgentRun
from app.models.tool_call_log import ToolCallLog
from app.services import travel_chat_service
from app.services.feature_service import FeatureFlagService
from app.services.travel_chat_service import (
    _stored_conversation_history,
    effective_client_today,
)
from tests.test_auth import auth_headers, register_user


def test_stored_conversation_history_excludes_current_message() -> None:
    conversation = SimpleNamespace(
        messages=[
            {"role": "user", "kind": "text", "text": "我想去云南玩一个星期"},
            {
                "role": "assistant",
                "kind": "questions",
                "text": "还需要确认：",
                "questions": ["这次一共几个人？"],
                "draft": {"destination": "云南"},
            },
            {
                "role": "user",
                "kind": "text",
                "text": "下个星期出发，我自己一个人",
            },
        ]
    )

    history = _stored_conversation_history(
        conversation,  # type: ignore[arg-type]
        current_message="下个星期出发，我自己一个人",
    )

    assert [turn.role for turn in history] == ["user", "assistant"]
    assert "一个星期" in history[0].content
    assert "这次一共几个人" in history[1].content
    assert "云南" in history[1].content


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


async def test_travel_chat_daily_cost_limit_blocks_before_model_call(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    owner_id = registration["user"]["id"]
    settings = Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        daily_user_cost_limit_minor=1,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.test_session.add(
        AgentRun(
            created_by=owner_id,
            trip_id=None,
            status="completed",
            progress=100,
            purpose="travel_chat",
            provider="mock",
            model_name="mock",
            estimated_cost_minor=10,
            events=[],
        )
    )
    await app.state.test_session.commit()
    try:
        response = await api_client.post(
            "/api/v1/chat/respond",
            headers=auth_headers(str(registration["access_token"])),
            json={"message": "重庆冬天怎么穿？", "history": []},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "cost_limit_exceeded"


async def test_travel_chat_returns_structured_transport_strategy(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={
            "message": (
                "2026年12月1日到12月3日，2个人从上海去重庆，"
                "全程自驾，预算5000元。"
            ),
            "history": [],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    strategy = payload["brief"]["transport_strategy"]
    assert strategy["strategy"] == "single"
    assert strategy["segments"][0]["mode"] == "self_drive"
    assert strategy["segments"][0]["coverage"] == "whole_trip"
    assert payload["brief"]["transport_preferences"] == ["全程自驾"]


async def test_travel_chat_accepts_citywalk_day_trip(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={
            "message": "帮我规划一次广州一日游，citywalk",
            "history": [],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "plan_trip"
    assert payload["in_scope"] is True
    assert payload["requires_planning"] is False
    assert payload["draft"]["destination"] == "广州"
    assert "start_date" in payload["missing_fields"]
    assert payload["questions"]


async def test_travel_chat_completes_day_trip_after_follow_up(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    headers = auth_headers(str(registration["access_token"]))
    first_message = "帮我规划一次广州一日游，citywalk"
    first_response = await api_client.post(
        "/api/v1/chat/respond",
        headers=headers,
        json={"message": first_message, "history": []},
    )

    assert first_response.status_code == 200, first_response.text
    assert first_response.json()["questions"]

    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=headers,
        json={
            "message": "2026年11月20日，1个人，预算500元。",
            "history": [
                {"role": "user", "content": first_message},
                {
                    "role": "assistant",
                    "content": "还需要确认日期、人数和预算。",
                },
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "plan_trip"
    assert payload["requires_planning"] is True
    assert payload["brief"]["destination"] == "广州"
    assert payload["brief"]["start_date"] == "2026-11-20"
    assert payload["brief"]["end_date"] == "2026-11-20"
    assert payload["brief"]["party_size"] == 1
    assert payload["brief"]["budget_minor"] == 50_000


async def test_date_only_reply_continues_active_planning(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    conversation = await api_client.post(
        "/api/v1/conversations",
        headers=auth_headers(token),
        json={
            "title": "西藏",
            "messages": [],
            "planning_draft": {
                "destination": "西藏",
                "party_size": 1,
                "budget_minor": 300_000,
            },
        },
    )
    assert conversation.status_code == 201, conversation.text

    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(token),
        json={
            "message": "2026年12月12日到19日",
            "conversation_id": conversation.json()["id"],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "plan_trip"
    assert payload["draft"]["destination"] == "西藏"
    assert payload["draft"]["start_date"] == "2026-12-12"
    assert payload["draft"]["end_date"] == "2026-12-19"
    assert payload["draft"]["party_size"] == 1
    assert payload["brief"]["budget_minor"] == 300_000
    assert payload["date_assumptions"]


async def test_follow_up_reuses_draft_destination_party_and_duration(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        travel_chat_service,
        "_shanghai_today",
        lambda: date(2026, 11, 15),
    )
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    conversation = await api_client.post(
        "/api/v1/conversations",
        headers=auth_headers(token),
        json={
            "title": "云南",
            "messages": [],
            "planning_draft": {
                "destination": "云南",
                "party_size": 1,
                "date_context": {"duration_days": 7},
            },
        },
    )

    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(token),
        json={
            "message": "下个星期出发",
            "conversation_id": conversation.json()["id"],
            "client_today": "2026-11-15",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "plan_trip"
    assert payload["requires_planning"] is True
    assert payload["draft"]["destination"] == "云南"
    assert payload["draft"]["party_size"] == 1
    assert payload["draft"]["start_date"] == "2026-11-16"
    assert payload["draft"]["end_date"] == "2026-11-22"
    assert payload["missing_fields"] == []
    assert payload["questions"] == []


async def test_create_this_itinerary_triggers_planning_from_complete_draft(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    conversation = await api_client.post(
        "/api/v1/conversations",
        headers=auth_headers(token),
        json={
            "title": "云南",
            "messages": [],
            "planning_draft": {
                "destination": "云南",
                "party_size": 1,
                "start_date": "2026-11-16",
                "end_date": "2026-11-22",
                "budget_minor": 500_000,
            },
        },
    )

    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(token),
        json={
            "message": "创建这个行程",
            "conversation_id": conversation.json()["id"],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "plan_trip"
    assert payload["requires_planning"] is True
    assert payload["questions"] == []
    assert payload["brief"]["destination"] == "云南"
    assert payload["brief"]["start_date"] == "2026-11-16"


def test_client_today_is_accepted_only_within_one_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        travel_chat_service,
        "_shanghai_today",
        lambda: date(2026, 11, 15),
    )

    assert effective_client_today(date(2026, 11, 16)) == date(2026, 11, 16)
    assert effective_client_today(date(2026, 11, 14)) == date(2026, 11, 14)
    assert effective_client_today(date(2026, 11, 17)) == date(2026, 11, 15)
    assert effective_client_today(None) == date(2026, 11, 15)


async def test_chat_uses_valid_client_today_for_relative_dates(
    api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        travel_chat_service,
        "_shanghai_today",
        lambda: date(2026, 11, 15),
    )
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    conversation = await api_client.post(
        "/api/v1/conversations",
        headers=auth_headers(token),
        json={
            "title": "成都",
            "messages": [],
            "planning_draft": {"destination": "成都", "party_size": 2},
        },
    )

    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(token),
        json={
            "message": "明天出发，玩3天",
            "conversation_id": conversation.json()["id"],
            "client_today": "2026-11-16",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["draft"]["start_date"] == "2026-11-17"
    assert payload["draft"]["end_date"] == "2026-11-19"


async def test_conversation_context_is_owner_isolated(
    api_client: httpx.AsyncClient,
) -> None:
    owner = await register_user(api_client)
    outsider = await register_user(api_client)
    conversation = await api_client.post(
        "/api/v1/conversations",
        headers=auth_headers(str(owner["access_token"])),
        json={
            "title": "私人草稿",
            "messages": [],
            "planning_draft": {"destination": "西藏"},
        },
    )

    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(outsider["access_token"])),
        json={
            "message": "2026年12月12日到19日",
            "conversation_id": conversation.json()["id"],
        },
    )

    assert response.status_code == 404


async def test_missing_conversation_context_returns_404(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={
            "message": "2026年12月12日到19日",
            "conversation_id": "00000000-0000-0000-0000-000000000001",
        },
    )

    assert response.status_code == 404


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


async def test_travel_chat_accepts_destination_food_question(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={"message": "广州有什么好吃的", "history": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == "destination_research"
    assert payload["in_scope"] is True
    assert payload["used_tools"]


async def test_budget_question_executes_budget_skill_end_to_end(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={"message": "泉州三天预算500元够吗", "history": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "calculate_budget" in payload["used_tools"]

    run = await app.state.test_session.scalar(
        select(AgentRun)
        .where(AgentRun.purpose == "travel_chat")
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    assert run is not None
    assert {
        item["name"] for item in run.skills_used
    } >= {"trip-intent-routing", "budget-optimization"}
    tool_calls = list(
        (
            await app.state.test_session.execute(
                select(ToolCallLog).where(
                    ToolCallLog.agent_run_id == run.id
                )
            )
        ).scalars()
    )
    assert {item.tool_name for item in tool_calls} == {
        "calculate_budget"
    }


async def test_chat_skill_execution_respects_global_skill_flag(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    owner_id = UUID(str(registration["user"]["id"]))
    await FeatureFlagService(app.state.test_session).toggle(
        key="agent_skills_enabled",
        enabled=False,
        actor_id=owner_id,
        reason="chat rollout disabled",
    )

    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(token),
        json={"message": "泉州三天预算500元够吗", "history": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["selected_skills"] == []
    assert payload["used_tools"] == []
    run = await app.state.test_session.scalar(
        select(AgentRun)
        .where(AgentRun.purpose == "travel_chat")
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    assert run is not None
    assert run.skills_used == []


async def test_attachment_question_executes_attachment_skill(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    uploaded = await api_client.post(
        "/api/v1/uploads",
        headers=auth_headers(token),
        files={
            "file": (
                "trip-notes.txt",
                "2026年12月1日到12月3日，2个人从上海去重庆。".encode(),
                "text/plain",
            )
        },
    )
    assert uploaded.status_code == 201, uploaded.text

    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(token),
        json={
            "message": "按附件整理旅行需求",
            "attachment_ids": [uploaded.json()["id"]],
            "history": [],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "extract_attachment" in payload["used_tools"]

    run = await app.state.test_session.scalar(
        select(AgentRun)
        .where(AgentRun.purpose == "travel_chat")
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    assert run is not None
    assert {
        item["name"] for item in run.skills_used
    } >= {"trip-intent-routing", "attachment-understanding"}


async def test_route_question_executes_route_skill_end_to_end(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={"message": "上海到重庆怎么走", "history": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert {"search_places", "get_route"} <= set(payload["used_tools"])

    run = await app.state.test_session.scalar(
        select(AgentRun)
        .where(AgentRun.purpose == "travel_chat")
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    assert run is not None
    assert {
        item["name"] for item in run.skills_used
    } >= {"trip-intent-routing", "route-optimization"}


async def test_food_question_executes_food_skill_end_to_end(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={"message": "重庆有什么好吃的", "history": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert {"search_places", "get_place_facts"} <= set(payload["used_tools"])

    run = await app.state.test_session.scalar(
        select(AgentRun)
        .where(AgentRun.purpose == "travel_chat")
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    assert run is not None
    assert {
        item["name"] for item in run.skills_used
    } >= {"trip-intent-routing", "food-planning"}


async def test_lodging_question_executes_lodging_skill_end_to_end(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={"message": "住重庆哪个区域方便", "history": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert {"search_places", "get_route"} <= set(payload["used_tools"])

    run = await app.state.test_session.scalar(
        select(AgentRun)
        .where(AgentRun.purpose == "travel_chat")
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    assert run is not None
    assert {
        item["name"] for item in run.skills_used
    } >= {"trip-intent-routing", "lodging-area-selection"}


async def test_authorized_memory_question_executes_memory_skill(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    created = await api_client.post(
        "/api/v1/memories",
        headers=auth_headers(token),
        json={
            "category": "lodging",
            "content": "住宿优先靠近地铁站",
            "consent": True,
        },
    )
    assert created.status_code == 201, created.text

    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(token),
        json={"message": "你还记得我的住宿偏好吗？", "history": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "get_authorized_memory_context" in payload["used_tools"]
    run = await app.state.test_session.scalar(
        select(AgentRun)
        .where(AgentRun.purpose == "travel_chat")
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    assert run is not None
    assert {
        item["name"] for item in run.skills_used
    } >= {"trip-intent-routing", "travel-memory"}


async def test_social_copy_request_executes_social_skill(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={
            "message": "帮我写一段泉州旅行朋友圈文案",
            "history": [],
        },
    )

    assert response.status_code == 200, response.text
    run = await app.state.test_session.scalar(
        select(AgentRun)
        .where(AgentRun.purpose == "travel_chat")
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    assert run is not None
    assert {
        item["name"] for item in run.skills_used
    } >= {"trip-intent-routing", "social-copywriting"}


@pytest.mark.parametrize(
    ("message", "expected_intent"),
    [
        ("成都到乐山怎么走", "route_advice"),
        ("12月去哈尔滨穿什么", "travel_question"),
        ("住成都哪个区域方便", "travel_question"),
        ("泉州三天预算3000够吗", "budget_advice"),
        ("去日本需要签证吗", "travel_question"),
        ("珠峰大本营高反风险大吗", "travel_question"),
    ],
)
async def test_travel_chat_routes_common_travel_questions(
    api_client: httpx.AsyncClient,
    message: str,
    expected_intent: str,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/chat/respond",
        headers=auth_headers(str(registration["access_token"])),
        json={"message": message, "history": []},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["intent"] == expected_intent
    assert payload["in_scope"] is True


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
