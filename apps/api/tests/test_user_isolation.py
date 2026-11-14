# 文件说明：后端自动化测试：test_user_isolation。
from uuid import uuid4

import httpx

from tests.test_auth import auth_headers, register_user


async def test_user_a_cannot_read_or_modify_user_b(api_client: httpx.AsyncClient) -> None:
    user_a = await register_user(
        api_client,
        email=f"user-a-{uuid4().hex}@example.com",
    )
    user_b = await register_user(
        api_client,
        email=f"user-b-{uuid4().hex}@example.com",
    )

    token_a = str(user_a["access_token"])
    token_b = str(user_b["access_token"])
    user_b_id = str(user_b["user"]["id"])

    read_b = await api_client.get(
        f"/api/v1/users/{user_b_id}",
        headers=auth_headers(token_a),
    )
    assert read_b.status_code == 404

    update_a = await api_client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token_a),
        json={"display_name": "Traveler A Updated"},
    )
    assert update_a.status_code == 200

    me_b = await api_client.get(
        "/api/v1/auth/me",
        headers=auth_headers(token_b),
    )
    assert me_b.status_code == 200
    assert me_b.json()["display_name"] == "Test Traveler"
