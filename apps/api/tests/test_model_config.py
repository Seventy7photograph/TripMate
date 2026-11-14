# 文件说明：后端自动化测试：test_model_config。
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.api.deps import get_settings
from app.core.config import Settings
from app.main import app
from app.models.model_config import AgentModelConfig
from app.services.model_config_service import ModelConfigService
from tests.test_admin_permissions import promote_admin
from tests.test_auth import auth_headers, register_user


async def test_model_config_requires_admin(api_client: httpx.AsyncClient) -> None:
    user = await register_user(api_client)
    response = await api_client.get(
        "/api/v1/admin/model-configs",
        headers=auth_headers(str(user["access_token"])),
    )
    assert response.status_code == 403


def test_production_rejects_mock_provider_profiles() -> None:
    with pytest.raises(ValueError, match="PROVIDER_PROFILE must be live"):
        Settings(
            app_env="production",
            provider_profile="mock",
            map_provider_profile="live",
            jwt_secret="x" * 64,
        )

    with pytest.raises(ValueError, match="MAP_PROVIDER_PROFILE must be live"):
        Settings(
            app_env="production",
            provider_profile="live",
            map_provider_profile="mock",
            jwt_secret="x" * 64,
        )


async def test_database_model_config_can_be_disabled_for_deterministic_runtime(
    api_client: httpx.AsyncClient,
) -> None:
    app.state.test_session.add(
        AgentModelConfig(
            stage="brief_parse",
            provider_profile="mock",
            base_url="https://llm.example.test/v1",
            model_name="database-only-model",
            timeout_seconds=30,
            max_retries=2,
        )
    )
    await app.state.test_session.commit()

    service = ModelConfigService(
        app.state.test_session,
        Settings(
            app_env="test",
            provider_profile="mock",
            map_provider_profile="mock",
            llm_model="environment-only-model",
            model_config_db_enabled=False,
        ),
    )

    resolved = await service.resolve("brief_parse")

    assert resolved.model_name == "environment-only-model"


async def test_admin_can_update_write_only_model_config(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await register_user(
        api_client,
        email=f"model-admin-{uuid4().hex}@example.com",
    )
    await promote_admin(str(admin["user"]["id"]))
    token = str(admin["access_token"])

    listed = await api_client.get(
        "/api/v1/admin/model-configs",
        headers=auth_headers(token),
    )
    assert listed.status_code == 200, listed.text
    assert {item["stage"] for item in listed.json()["items"]} == {
        "brief_parse",
        "research_planner",
        "itinerary_composer",
        "travel_chat",
    }
    assert all("api_key" not in item for item in listed.json()["items"])

    updated = await api_client.patch(
        "/api/v1/admin/model-configs/brief_parse",
        headers=auth_headers(token),
        json={
            "provider_profile": "live",
            "base_url": "https://llm.example.test/v1",
            "model_name": "planner-small",
            "api_key": "write-only-secret",
            "timeout_seconds": 20,
            "max_retries": 1,
        },
    )
    assert updated.status_code == 200, updated.text
    payload = updated.json()
    assert payload["provider_profile"] == "live"
    assert payload["model_name"] == "planner-small"
    assert payload["api_key_configured"] is True
    assert "write-only-secret" not in updated.text

    model = await app.state.test_session.scalar(
        select(AgentModelConfig).where(AgentModelConfig.stage == "brief_parse")
    )
    assert model is not None
    assert model.api_key_ciphertext
    assert "write-only-secret" not in model.api_key_ciphertext
    resolved = await ModelConfigService(
        app.state.test_session,
        get_settings(),
    ).resolve("brief_parse")
    assert resolved.provider_profile == "live"
    assert resolved.base_url == "https://llm.example.test/v1"
    assert resolved.model_name == "planner-small"
    assert resolved.api_key is not None
    assert resolved.api_key.get_secret_value() == "write-only-secret"

    audits = await api_client.get(
        "/api/v1/admin/audit-logs",
        headers=auth_headers(token),
    )
    assert audits.status_code == 200
    assert "write-only-secret" not in audits.text


async def test_admin_model_config_rejects_mock_profile(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await register_user(
        api_client,
        email=f"model-profile-admin-{uuid4().hex}@example.com",
    )
    await promote_admin(str(admin["user"]["id"]))

    response = await api_client.patch(
        "/api/v1/admin/model-configs/brief_parse",
        headers=auth_headers(str(admin["access_token"])),
        json={
            "provider_profile": "mock",
            "base_url": "https://api.deepseek.com",
            "model_name": "mock-tripbrief-v1",
            "timeout_seconds": 30,
            "max_retries": 2,
        },
    )

    assert response.status_code == 422


async def test_brief_parse_uses_admin_model_override_at_runtime(
    api_client: httpx.AsyncClient,
) -> None:
    user = await register_user(api_client)
    user_token = str(user["access_token"])

    app.state.test_session.add(
        AgentModelConfig(
            stage="brief_parse",
            provider_profile="mock",
            base_url="https://api.deepseek.com",
            model_name="mock-tripbrief-v1",
            timeout_seconds=30,
            max_retries=2,
        )
    )
    await app.state.test_session.commit()

    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="test",
        provider_profile="live",
        map_provider_profile="mock",
        llm_api_key=None,
        llm_model="missing-live-model",
    )
    try:
        parsed = await api_client.post(
            "/api/v1/briefs/parse",
            headers=auth_headers(user_token),
            json={
                "text": "2026年12月1日到12月3日，2个人去重庆，预算5000元。"
            },
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["brief"]["destination"] == "重庆"


async def test_model_config_rejects_private_provider_url(
    api_client: httpx.AsyncClient,
) -> None:
    admin = await register_user(
        api_client,
        email=f"model-ssrf-admin-{uuid4().hex}@example.com",
    )
    await promote_admin(str(admin["user"]["id"]))

    response = await api_client.patch(
        "/api/v1/admin/model-configs/brief_parse",
        headers=auth_headers(str(admin["access_token"])),
        json={
            "provider_profile": "live",
            "base_url": "http://127.0.0.1:9000/v1",
            "model_name": "internal-model",
            "api_key": "secret",
            "timeout_seconds": 30,
            "max_retries": 2,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsafe_model_url"
