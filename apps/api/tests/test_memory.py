# 文件说明：后端自动化测试：test_memory。
from uuid import UUID, uuid4

import httpx

from app.main import app
from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


async def test_memory_requires_explicit_consent(api_client: httpx.AsyncClient) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    response = await api_client.post(
        "/api/v1/memories",
        headers=auth_headers(token),
        json={
            "category": "preference",
            "content": "喜欢安静的住宿区域",
            "consent": False,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "memory_consent_required"


async def test_memory_can_be_listed_edited_and_disabled(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    created = await api_client.post(
        "/api/v1/memories",
        headers=auth_headers(token),
        json={
            "category": "food",
            "content": "不吃香菜，偏好当地早餐",
            "consent": True,
        },
    )
    assert created.status_code == 201, created.text
    memory = created.json()
    assert memory["content"] == "不吃香菜，偏好当地早餐"
    assert memory["enabled"] is True
    assert memory["consent_at"]
    assert "embedding" not in memory

    listed = await api_client.get("/api/v1/memories", headers=auth_headers(token))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [memory["id"]]

    updated = await api_client.patch(
        f"/api/v1/memories/{memory['id']}",
        headers=auth_headers(token),
        json={
            "content": "不吃香菜，早餐优先本地小店",
            "enabled": False,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["content"] == "不吃香菜，早餐优先本地小店"
    assert updated.json()["enabled"] is False


async def test_memory_is_owner_isolated(api_client: httpx.AsyncClient) -> None:
    owner = await register_user(
        api_client,
        email=f"memory-owner-{uuid4().hex}@example.com",
    )
    outsider = await register_user(
        api_client,
        email=f"memory-outsider-{uuid4().hex}@example.com",
    )

    created = await api_client.post(
        "/api/v1/memories",
        headers=auth_headers(str(owner["access_token"])),
        json={
            "category": "mobility",
            "content": "走路超过 30 分钟需要休息",
            "consent": True,
        },
    )
    memory_id = created.json()["id"]

    listed = await api_client.get(
        "/api/v1/memories",
        headers=auth_headers(str(outsider["access_token"])),
    )
    assert listed.status_code == 200
    assert listed.json() == []

    updated = await api_client.patch(
        f"/api/v1/memories/{memory_id}",
        headers=auth_headers(str(outsider["access_token"])),
        json={"enabled": False},
    )
    assert updated.status_code == 404

    deleted = await api_client.delete(
        f"/api/v1/memories/{memory_id}",
        headers=auth_headers(str(outsider["access_token"])),
    )
    assert deleted.status_code == 404


async def test_deleted_memory_is_not_retrieved_for_planning(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    owner_id = UUID(str(registration["user"]["id"]))

    created = await api_client.post(
        "/api/v1/memories",
        headers=auth_headers(token),
        json={
            "category": "preference",
            "content": "住宿优先靠近地铁站",
            "consent": True,
        },
    )
    assert created.status_code == 201, created.text

    from app.services.memory_service import MemoryService

    service = MemoryService(app.state.test_session)
    before_delete = await service.retrieval_constraints(
        owner_id=owner_id,
        query="上海 地铁 住宿",
    )
    assert any("靠近地铁站" in item for item in before_delete)

    deleted = await api_client.delete(
        f"/api/v1/memories/{created.json()['id']}",
        headers=auth_headers(token),
    )
    assert deleted.status_code == 204

    after_delete = await service.retrieval_constraints(
        owner_id=owner_id,
        query="上海 地铁 住宿",
    )
    assert after_delete == []


async def test_clear_all_memories_removes_every_record(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    for content in ("喜欢自然风光", "不吃辣"):
        created = await api_client.post(
            "/api/v1/memories",
            headers=auth_headers(token),
            json={"category": "preference", "content": content, "consent": True},
        )
        assert created.status_code == 201, created.text

    cleared = await api_client.delete("/api/v1/memories", headers=auth_headers(token))
    assert cleared.status_code == 204

    listed = await api_client.get("/api/v1/memories", headers=auth_headers(token))
    assert listed.json() == []


async def test_planning_event_reports_applied_authorized_memory(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(destination="重庆", must_visit=["洪崖洞"]),
        )
    ).json()
    memory = await api_client.post(
        "/api/v1/memories",
        headers=auth_headers(token),
        json={
            "category": "lodging",
            "content": "住宿优先靠近地铁站",
            "consent": True,
        },
    )
    assert memory.status_code == 201, memory.text

    started = await api_client.post(
        f"/api/v1/trips/{trip['id']}/plan",
        headers=auth_headers(token),
        json={"expected_version": 1},
    )
    assert started.status_code == 202, started.text
    job = await api_client.get(
        f"/api/v1/jobs/{started.json()['job_id']}",
        headers=auth_headers(token),
    )
    assert job.status_code == 200, job.text
    events = job.json()["events"]
    assert any(event.get("stage") == "memory_applied" for event in events)
    assert [event["sequence"] for event in events] == list(
        range(1, len(events) + 1)
    )
