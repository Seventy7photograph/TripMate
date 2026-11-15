# 文件说明：后端自动化测试：planning_draft 对话契约与 CRUD。
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from app.schemas.conversation import ConversationResponse
from app.schemas.planning_draft import PlanningDraft
from tests.test_auth import auth_headers, register_user


def test_planning_draft_defaults_to_empty_state() -> None:
    draft = PlanningDraft()

    assert draft.destination is None
    assert draft.start_date is None
    assert draft.party_size is None
    assert draft.pending_questions == []


def test_conversation_response_preserves_planning_draft() -> None:
    response = ConversationResponse.model_validate(
        {
            "id": uuid4(),
            "title": "成都",
            "messages": [],
            "requirement_history": [],
            "planning_draft": {"destination": "成都"},
            "trip_id": None,
            "version": 1,
            "message_count": 0,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    )

    assert response.planning_draft["destination"] == "成都"


async def test_conversation_crud_preserves_planning_draft(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    headers = auth_headers(str(registration["access_token"]))

    created = await api_client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "title": "成都",
            "messages": [],
            "requirement_history": [],
            "planning_draft": {
                "destination": "成都",
                "pending_questions": ["还需要确认出发日期"],
            },
        },
    )

    assert created.status_code == 201, created.text
    conversation = created.json()
    conversation_id = conversation["id"]
    assert conversation["planning_draft"]["destination"] == "成都"
    assert conversation["planning_draft"]["pending_questions"] == ["还需要确认出发日期"]

    updated = await api_client.patch(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
        json={
            "expected_version": 1,
            "title": "成都四天",
            "messages": [],
            "requirement_history": [],
            "planning_draft": {
                "destination": "成都",
                "start_date": "2026-12-12",
                "end_date": "2026-12-15",
                "party_size": 2,
                "budget_minor": 500_000,
                "pending_questions": [],
            },
        },
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["planning_draft"]["party_size"] == 2
    assert updated.json()["planning_draft"]["budget_minor"] == 500_000

    loaded = await api_client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=headers,
    )
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["planning_draft"]["start_date"] == "2026-12-12"

    listed = await api_client.get("/api/v1/conversations", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["planning_draft"]["destination"] == "成都"


async def test_conversation_update_without_draft_preserves_existing_state(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    headers = auth_headers(str(registration["access_token"]))
    created = (
        await api_client.post(
            "/api/v1/conversations",
            headers=headers,
            json={
                "title": "成都",
                "messages": [],
                "requirement_history": [],
                "planning_draft": {"destination": "成都"},
            },
        )
    ).json()

    updated = await api_client.patch(
        f"/api/v1/conversations/{created['id']}",
        headers=headers,
        json={
            "expected_version": 1,
            "title": "成都继续",
            "messages": [],
            "requirement_history": [],
        },
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["planning_draft"] == {"destination": "成都"}
