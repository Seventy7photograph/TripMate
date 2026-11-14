# 文件说明：后端自动化测试：test_conversations。
from uuid import uuid4

import httpx

from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


def conversation_messages(count: int) -> list[dict[str, object]]:
    return [
        {
            "role": "user",
            "kind": "text",
            "text": f"第 {index + 1} 轮补充：想去城市漫步。",
        }
        for index in range(count)
    ]


async def test_conversation_history_is_persisted_and_can_continue(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    messages = conversation_messages(2)

    created = await api_client.post(
        "/api/v1/conversations",
        headers=auth_headers(token),
        json={
            "title": "重庆三日",
            "messages": messages,
            "requirement_history": [
                "2个人从上海去重庆，喜欢夜景。",
                "预算5000元。",
            ],
        },
    )
    assert created.status_code == 201, created.text
    conversation = created.json()
    assert conversation["version"] == 1
    assert conversation["message_count"] == 2

    conversation_id = conversation["id"]
    updated = await api_client.patch(
        f"/api/v1/conversations/{conversation_id}",
        headers=auth_headers(token),
        json={
            "expected_version": 1,
            "title": "重庆三日继续规划",
            "messages": [
                *messages,
                {
                    "role": "assistant",
                    "kind": "questions",
                    "text": "还需要确认：",
                    "questions": ["这次旅行准备住哪个区域？"],
                },
            ],
            "requirement_history": [
                "2个人从上海去重庆，喜欢夜景。",
                "预算5000元。",
                "住解放碑附近。",
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert updated.json()["message_count"] == 3

    listed = await api_client.get(
        "/api/v1/conversations",
        headers=auth_headers(token),
    )
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [conversation_id]
    assert listed.json()["items"][0]["title"] == "重庆三日继续规划"

    loaded = await api_client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=auth_headers(token),
    )
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["messages"][-1]["questions"] == [
        "这次旅行准备住哪个区域？"
    ]
    assert loaded.json()["requirement_history"][-1] == "住解放碑附近。"


async def test_conversation_supports_more_than_twenty_turns(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(
        api_client,
        email=f"conversation-limit-{uuid4().hex}@example.com",
    )
    response = await api_client.post(
        "/api/v1/conversations",
        headers=auth_headers(str(registration["access_token"])),
        json={
            "title": "长对话",
            "messages": conversation_messages(60),
            "requirement_history": [f"第 {index + 1} 轮" for index in range(60)],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["message_count"] == 60


async def test_conversation_persists_answer_sources(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    response = await api_client.post(
        "/api/v1/conversations",
        headers=auth_headers(str(registration["access_token"])),
        json={
            "title": "泉州古建",
            "messages": [
                {
                    "role": "assistant",
                    "kind": "answer",
                    "text": "开元寺是泉州重要古建。",
                    "intent": "destination_research",
                    "sources": [
                        {
                            "url": "https://example.com/quanzhou",
                            "title": "泉州文旅",
                        }
                    ],
                    "used_tools": ["search_places"],
                }
            ],
            "requirement_history": ["泉州古建怎么玩？"],
        },
    )

    assert response.status_code == 201, response.text
    message = response.json()["messages"][0]
    assert message["kind"] == "answer"
    assert message["sources"][0]["url"] == "https://example.com/quanzhou"
    assert message["used_tools"] == ["search_places"]


async def test_conversation_access_is_owner_isolated(
    api_client: httpx.AsyncClient,
) -> None:
    owner = await register_user(
        api_client,
        email=f"conversation-owner-{uuid4().hex}@example.com",
    )
    outsider = await register_user(
        api_client,
        email=f"conversation-outsider-{uuid4().hex}@example.com",
    )
    created = await api_client.post(
        "/api/v1/conversations",
        headers=auth_headers(str(owner["access_token"])),
        json={"title": "私人对话", "messages": conversation_messages(1)},
    )
    conversation_id = created.json()["id"]

    response = await api_client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=auth_headers(str(outsider["access_token"])),
    )
    assert response.status_code == 404


async def test_conversation_cannot_reference_another_users_trip(
    api_client: httpx.AsyncClient,
) -> None:
    owner = await register_user(
        api_client,
        email=f"conversation-trip-owner-{uuid4().hex}@example.com",
    )
    outsider = await register_user(
        api_client,
        email=f"conversation-trip-outsider-{uuid4().hex}@example.com",
    )
    owner_token = str(owner["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(owner_token),
            json=trip_payload(),
        )
    ).json()

    response = await api_client.post(
        "/api/v1/conversations",
        headers=auth_headers(str(outsider["access_token"])),
        json={
            "title": "越权引用",
            "messages": conversation_messages(1),
            "trip_id": trip["id"],
        },
    )
    assert response.status_code == 404


async def test_conversation_rejects_oversized_transcript(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(
        api_client,
        email=f"conversation-size-{uuid4().hex}@example.com",
    )
    response = await api_client.post(
        "/api/v1/conversations",
        headers=auth_headers(str(registration["access_token"])),
        json={
            "title": "过大对话",
            "messages": [
                {
                    "role": "user",
                    "kind": "text",
                    "text": "x" * 12_000,
                }
                for _ in range(180)
            ],
        },
    )
    assert response.status_code == 422
