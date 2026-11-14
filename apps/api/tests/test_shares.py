# 文件说明：后端自动化测试：test_shares。
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from sqlalchemy import select

from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


async def create_shared_trip(api_client: httpx.AsyncClient):
    registration = await register_user(
        api_client,
        email=f"share-{uuid4().hex}@example.com",
    )
    token = str(registration["access_token"])
    headers = auth_headers(token)
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=headers,
            json=trip_payload(destination="重庆", start_date="2026-12-01", end_date="2026-12-01"),
        )
    ).json()
    day = (
        await api_client.post(
            f"/api/v1/trips/{trip['id']}/days",
            headers=headers,
            json={"expected_version": 1, "date": "2026-12-01"},
        )
    ).json()
    stop = (
        await api_client.post(
            f"/api/v1/days/{day['id']}/stops",
            headers=headers,
            json={
                "expected_version": 2,
                "place_id": "B001",
                "place_name": "洪崖洞",
                "start_at": "2026-12-01T09:00:00",
                "duration_minutes": 90,
                "estimated_cost_minor": 5000,
            },
        )
    ).json()
    return registration, token, trip, day, stop


async def test_share_create_public_read_and_privacy(
    api_client: httpx.AsyncClient,
) -> None:
    registration, token, trip, _, _ = await create_shared_trip(api_client)
    created = await api_client.post(
        f"/api/v1/trips/{trip['id']}/shares",
        headers=auth_headers(token),
        json={"expires_in_days": 30},
    )
    assert created.status_code == 201, created.text
    share = created.json()
    assert share["token"]
    assert share["url_path"] == f"/share/{share['token']}"

    public = await api_client.get(
        f"/api/v1/public/trips/{share['token']}",
    )
    assert public.status_code == 200, public.text
    payload = public.json()
    assert payload["destination"] == "重庆"
    assert payload["version"] == 3
    serialized = public.text
    assert registration["user"]["id"] not in serialized
    assert "owner_id" not in serialized
    assert "budget_minor" not in serialized
    assert "constraints" not in serialized
    assert "expenses" not in serialized

    from app.main import app
    from app.models.share_link import ShareLink

    stored = await app.state.test_session.scalar(
        select(ShareLink).where(ShareLink.id == share["id"])
    )
    assert stored is not None
    assert stored.token_hash != share["token"]


async def test_share_snapshot_stays_read_only_and_can_be_revoked(
    api_client: httpx.AsyncClient,
) -> None:
    _, token, trip, day, _ = await create_shared_trip(api_client)
    share = (
        await api_client.post(
            f"/api/v1/trips/{trip['id']}/shares",
            headers=auth_headers(token),
            json={},
        )
    ).json()
    await api_client.post(
        f"/api/v1/days/{day['id']}/stops",
        headers=auth_headers(token),
        json={
            "expected_version": 3,
            "place_id": "B002",
            "place_name": "解放碑",
            "start_at": "2026-12-01T13:00:00",
            "duration_minutes": 60,
            "estimated_cost_minor": 0,
        },
    )
    public = await api_client.get(f"/api/v1/public/trips/{share['token']}")
    assert len(public.json()["days"][0]["stops"]) == 1

    revoked = await api_client.delete(
        f"/api/v1/shares/{share['id']}",
        headers=auth_headers(token),
    )
    assert revoked.status_code == 204
    assert (await api_client.get(f"/api/v1/public/trips/{share['token']}")).status_code == 404


async def test_expired_share_is_not_public(
    api_client: httpx.AsyncClient,
) -> None:
    _, token, trip, _, _ = await create_shared_trip(api_client)
    share = (
        await api_client.post(
            f"/api/v1/trips/{trip['id']}/shares",
            headers=auth_headers(token),
            json={},
        )
    ).json()
    from app.main import app
    from app.models.share_link import ShareLink

    stored = await app.state.test_session.scalar(
        select(ShareLink).where(ShareLink.id == share["id"])
    )
    assert stored is not None
    stored.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await app.state.test_session.commit()

    response = await api_client.get(f"/api/v1/public/trips/{share['token']}")
    assert response.status_code == 404


async def test_favorites_are_idempotent_owner_isolated_and_removable(
    api_client: httpx.AsyncClient,
) -> None:
    owner = await register_user(
        api_client,
        email=f"favorite-owner-{uuid4().hex}@example.com",
    )
    outsider = await register_user(
        api_client,
        email=f"favorite-outsider-{uuid4().hex}@example.com",
    )
    owner_token = str(owner["access_token"])
    payload = {
        "kind": "place",
        "target_id": "B001",
        "label": "洪崖洞",
        "folder": "重庆灵感",
        "note": "夜景优先",
        "metadata": {"address": "重庆市渝中区"},
    }
    first = await api_client.post(
        "/api/v1/favorites",
        headers=auth_headers(owner_token),
        json=payload,
    )
    second = await api_client.post(
        "/api/v1/favorites",
        headers=auth_headers(owner_token),
        json=payload,
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]

    listed = await api_client.get(
        "/api/v1/favorites?kind=place&folder=重庆灵感",
        headers=auth_headers(owner_token),
    )
    assert [item["target_id"] for item in listed.json()] == ["B001"]
    assert listed.json()[0]["folder"] == "重庆灵感"
    assert listed.json()[0]["note"] == "夜景优先"

    updated = await api_client.patch(
        f"/api/v1/favorites/{first.json()['id']}",
        headers=auth_headers(owner_token),
        json={"folder": "夜景收藏", "note": "下次带相机"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["folder"] == "夜景收藏"
    assert updated.json()["note"] == "下次带相机"
    outsider_delete = await api_client.delete(
        f"/api/v1/favorites/{first.json()['id']}",
        headers=auth_headers(str(outsider["access_token"])),
    )
    assert outsider_delete.status_code == 404
    deleted = await api_client.delete(
        f"/api/v1/favorites/{first.json()['id']}",
        headers=auth_headers(owner_token),
    )
    assert deleted.status_code == 204


async def test_place_favorite_gets_a_kind_specific_default_folder(
    api_client: httpx.AsyncClient,
) -> None:
    owner = await register_user(
        api_client,
        email=f"favorite-default-{uuid4().hex}@example.com",
    )
    response = await api_client.post(
        "/api/v1/favorites",
        headers=auth_headers(str(owner["access_token"])),
        json={
            "kind": "place",
            "target_id": "B002",
            "label": "泉州开元寺",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["folder"] == "地点收藏"


async def test_trip_favorite_requires_trip_ownership(
    api_client: httpx.AsyncClient,
) -> None:
    owner = await register_user(
        api_client,
        email=f"favorite-trip-owner-{uuid4().hex}@example.com",
    )
    outsider = await register_user(
        api_client,
        email=f"favorite-trip-outsider-{uuid4().hex}@example.com",
    )
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(str(owner["access_token"])),
            json=trip_payload(),
        )
    ).json()
    response = await api_client.post(
        "/api/v1/favorites",
        headers=auth_headers(str(outsider["access_token"])),
        json={"kind": "trip", "target_id": trip["id"], "label": "越权收藏"},
    )
    assert response.status_code == 404
