# 文件说明：后端自动化测试：test_upload。
import base64
from io import BytesIO
from uuid import uuid4

import httpx
from PIL import Image

from app.api.deps import get_settings
from app.core.config import Settings
from app.main import app
from tests.test_auth import auth_headers, register_user


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (4, 4), color=(30, 90, 140)).save(buffer, format="PNG")
    return buffer.getvalue()


async def test_upload_rejects_unsupported_and_invalid_image(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    unsupported = await api_client.post(
        "/api/v1/uploads",
        headers=auth_headers(token),
        files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
    )
    assert unsupported.status_code == 415

    invalid_image = await api_client.post(
        "/api/v1/uploads",
        headers=auth_headers(token),
        files={"file": ("fake.png", b"not an image", "image/png")},
    )
    assert invalid_image.status_code == 422


async def test_upload_and_content_are_owner_isolated(
    api_client: httpx.AsyncClient,
) -> None:
    owner = await register_user(
        api_client,
        email=f"upload-owner-{uuid4().hex}@example.com",
    )
    outsider = await register_user(
        api_client,
        email=f"upload-outsider-{uuid4().hex}@example.com",
    )

    uploaded = await api_client.post(
        "/api/v1/uploads",
        headers=auth_headers(str(owner["access_token"])),
        files={"file": ("重庆.png", png_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    asset = uploaded.json()
    assert asset["kind"] == "image"
    assert asset["mime_type"] == "image/png"
    assert "storage_key" not in asset

    owner_content = await api_client.get(
        f"/api/v1/uploads/{asset['id']}/content",
        headers=auth_headers(str(owner["access_token"])),
    )
    assert owner_content.status_code == 200
    assert owner_content.headers["content-type"].startswith("image/png")
    assert owner_content.headers["x-content-type-options"] == "nosniff"

    outsider_content = await api_client.get(
        f"/api/v1/uploads/{asset['id']}/content",
        headers=auth_headers(str(outsider["access_token"])),
    )
    assert outsider_content.status_code == 404


async def test_upload_size_limit_is_enforced(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        max_document_upload_bytes=16,
        max_image_upload_bytes=16,
    )
    try:
        response = await api_client.post(
            "/api/v1/uploads",
            headers=auth_headers(token),
            files={"file": ("notes.txt", b"x" * 64, "text/plain")},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)
    assert response.status_code == 413


async def test_document_attachment_can_supply_requirement_text(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    text = (
        "2026年12月1日到12月3日，2个人从上海去重庆，"
        "预算5000元，喜欢美食和夜景。"
    ).encode()
    uploaded = await api_client.post(
        "/api/v1/uploads",
        headers=auth_headers(token),
        files={"file": ("trip-notes.txt", text, "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text

    parsed = await api_client.post(
        "/api/v1/briefs/parse",
        headers=auth_headers(token),
        json={"text": "", "attachment_ids": [uploaded.json()["id"]]},
    )
    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["brief"]["destination"] == "重庆"


async def test_large_image_is_downscaled_before_model_delivery(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    buffer = BytesIO()
    Image.new("RGB", (600, 300), color=(40, 100, 150)).save(buffer, format="PNG")

    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        max_image_dimension=256,
    )
    try:
        uploaded = await api_client.post(
            "/api/v1/uploads",
            headers=auth_headers(token),
            files={"file": ("large.png", buffer.getvalue(), "image/png")},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["mime_type"] == "image/webp"


async def test_upload_filename_is_sanitized_for_rendering(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    uploaded = await api_client.post(
        "/api/v1/uploads",
        headers=auth_headers(token),
        files={
            "file": (
                '<img src=x onerror="alert(1)">.txt',
                b"trip notes",
                "text/plain",
            )
        },
    )

    assert uploaded.status_code == 201, uploaded.text
    assert "<img" not in uploaded.json()["name"]
    assert "onerror" in uploaded.json()["name"]


def test_minimal_png_fixture_is_valid() -> None:
    assert png_bytes().startswith(b"\x89PNG")
    assert base64.b64encode(png_bytes()).startswith(b"iVBOR")
