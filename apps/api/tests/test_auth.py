# 文件说明：后端自动化测试：test_auth。
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def register_user(
    client: httpx.AsyncClient,
    *,
    email: str | None = None,
    password: str = "correct-horse-battery-staple",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email or f"user-{uuid4().hex}@example.com",
            "password": password,
            "display_name": "Test Traveler",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_register_login_me_and_update_profile(api_client: httpx.AsyncClient) -> None:
    email = f"auth-{uuid4().hex}@example.com"
    password = "correct-horse-battery-staple"
    registration = await register_user(api_client, email=email, password=password)

    assert registration["token_type"] == "bearer"
    assert registration["user"]["email"] == email
    assert "password_hash" not in registration["user"]

    token = str(registration["access_token"])
    me = await api_client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["id"] == registration["user"]["id"]

    wrong_password = await api_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "this-is-the-wrong-password"},
    )
    assert wrong_password.status_code == 401

    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": email.upper(), "password": password},
    )
    assert login.status_code == 200

    update = await api_client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={
            "display_name": "Updated Traveler",
            "default_origin": "Shanghai",
            "currency": "CNY",
            "language": "zh-CN",
        },
    )
    assert update.status_code == 200
    assert update.json()["display_name"] == "Updated Traveler"
    assert update.json()["default_origin"] == "Shanghai"

    clear_origin = await api_client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"default_origin": None},
    )
    assert clear_origin.status_code == 200
    assert clear_origin.json()["default_origin"] is None


async def test_duplicate_email_is_rejected(api_client: httpx.AsyncClient) -> None:
    email = f"duplicate-{uuid4().hex}@example.com"
    await register_user(api_client, email=email)

    duplicate = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": email.upper(),
            "password": "correct-horse-battery-staple",
            "display_name": "Duplicate User",
        },
    )

    assert duplicate.status_code == 409


async def test_expired_token_is_rejected(api_client: httpx.AsyncClient) -> None:
    import jwt

    from app.core.config import get_settings

    registration = await register_user(api_client)
    settings = get_settings()
    expired_token = jwt.encode(
        {
            "sub": str(registration["user"]["id"]),
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "iss": "tripmate",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    response = await api_client.get(
        "/api/v1/auth/me",
        headers=auth_headers(expired_token),
    )

    assert response.status_code == 401


async def test_missing_token_is_rejected(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_logout_revokes_access_token_immediately(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    logout = await api_client.post(
        "/api/v1/auth/logout",
        headers=auth_headers(token),
    )

    assert logout.status_code == 204, logout.text
    me = await api_client.get(
        "/api/v1/auth/me",
        headers=auth_headers(token),
    )
    assert me.status_code == 401
