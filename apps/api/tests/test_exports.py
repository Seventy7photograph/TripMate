# 文件说明：后端自动化测试：test_exports。
from uuid import uuid4

import httpx

from tests.test_auth import auth_headers, register_user
from tests.test_shares import create_shared_trip


async def test_export_document_matches_current_version_and_stops(
    api_client: httpx.AsyncClient,
) -> None:
    _, token, trip, _, _ = await create_shared_trip(api_client)
    response = await api_client.get(
        f"/api/v1/trips/{trip['id']}/export",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.text
    document = response.json()
    assert document["version"] == 3
    assert document["destination"] == "重庆"
    assert document["filename"] == "tripmate-重庆-3"
    assert document["days"][0]["stops"][0]["place_name"] == "洪崖洞"
    assert "owner_id" not in response.text
    assert "budget_minor" not in response.text

    outsider = await register_user(
        api_client,
        email=f"export-outsider-{uuid4().hex}@example.com",
    )
    forbidden = await api_client.get(
        f"/api/v1/trips/{trip['id']}/export",
        headers=auth_headers(str(outsider["access_token"])),
    )
    assert forbidden.status_code == 404
