# 文件说明：后端自动化测试：test_skill_registry。
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest

from app.api.deps import get_settings
from app.core.config import Settings
from app.main import app
from app.skills.manifest import SkillManifestError
from app.skills.registry import SkillNotFoundError, SkillRegistry
from app.skills.state_service import SkillStateService
from tests.test_admin_permissions import promote_admin
from tests.test_auth import auth_headers, register_user


def write_manifest(
    root: Path,
    name: str = "route-optimization",
    *,
    version: str = "1.0.0",
    status: str = "active",
    allowed_tools: list[str] | None = None,
    extra_yaml: str = "",
) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    tools = allowed_tools or ["get_route"]
    tool_lines = "".join(f"  - {tool}\n" for tool in tools)
    manifest = skill_dir / "skill.yaml"
    manifest.write_text(
        (
            f"name: {name}\n"
            f"version: {version}\n"
            f"status: {status}\n"
            "description: Build a feasible route order from verified places.\n"
            "allowed_tools:\n"
            f"{tool_lines}"
            "allowed_mcp_connectors: []\n"
            "max_tool_calls: 8\n"
            "timeout_seconds: 40\n"
            "max_tokens: 1200\n"
            "fallback: existing_itinerary_graph\n"
            f"{extra_yaml}"
        ),
        encoding="utf-8",
    )
    return manifest


def test_registry_selects_latest_or_explicit_version(tmp_path: Path) -> None:
    write_manifest(tmp_path, version="1.2.0")
    registry = SkillRegistry(known_tools={"get_route"})

    registry.load(tmp_path)

    assert registry.get("route-optimization").version == "1.2.0"
    assert registry.get("route-optimization", "1.2.0").version == "1.2.0"
    with pytest.raises(SkillNotFoundError):
        registry.get("missing-skill")


def test_registry_rejects_script_fields(tmp_path: Path) -> None:
    write_manifest(tmp_path, extra_yaml="script: rm -rf /\n")

    with pytest.raises(SkillManifestError):
        SkillRegistry(known_tools={"get_route"}).load(tmp_path)


def test_registry_rejects_name_directory_mismatch(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path)
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "name: route-optimization",
            "name: budget-optimization",
        ),
        encoding="utf-8",
    )

    with pytest.raises(SkillManifestError):
        SkillRegistry(known_tools={"get_route"}).load(tmp_path)


def test_registry_rejects_unsafe_yaml_tag(tmp_path: Path) -> None:
    skill_dir = tmp_path / "unsafe-skill"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text(
        "!!python/object/apply:os.system ['echo unsafe']\n",
        encoding="utf-8",
    )

    with pytest.raises(SkillManifestError):
        SkillRegistry(known_tools={"get_route"}).load(tmp_path)


def test_registry_load_is_atomic(tmp_path: Path) -> None:
    registry = SkillRegistry(known_tools={"get_route"})
    write_manifest(tmp_path)
    registry.load(tmp_path)
    write_manifest(
        tmp_path,
        name="budget-optimization",
        allowed_tools=["shell_exec"],
    )

    with pytest.raises(SkillManifestError):
        registry.load(tmp_path)

    assert registry.get("route-optimization").version == "1.0.0"


def test_registry_rejects_symbolic_link_escape(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    write_manifest(outside, name="escaped-skill", allowed_tools=["get_route"])
    linked = root / "escaped-skill"
    try:
        linked.symlink_to(outside / "escaped-skill", target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links are unavailable")

    with pytest.raises(SkillManifestError):
        SkillRegistry(known_tools={"get_route"}).load(root)


async def test_disabled_skill_is_not_returned(
    api_client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    write_manifest(tmp_path)
    registry = SkillRegistry(known_tools={"get_route"})
    registry.load(tmp_path)
    actor = await register_user(api_client)
    admin_id = UUID(str(actor["user"]["id"]))
    service = SkillStateService(app.state.test_session)

    await service.set_enabled(
        skill_name="route-optimization",
        version="1.0.0",
        enabled=False,
        actor_id=admin_id,
        reason="maintenance",
    )

    enabled = await service.enabled_manifests(registry)

    assert "route-optimization" not in {skill.name for skill in enabled}


async def test_state_from_other_version_does_not_disable_new_manifest(
    api_client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    write_manifest(tmp_path, version="1.1.0")
    registry = SkillRegistry(known_tools={"get_route"})
    registry.load(tmp_path)
    actor = await register_user(api_client)
    service = SkillStateService(app.state.test_session)
    await service.set_enabled(
        skill_name="route-optimization",
        version="1.0.0",
        enabled=False,
        actor_id=UUID(str(actor["user"]["id"])),
        reason="old-version",
    )

    enabled = await service.enabled_manifests(registry)

    assert {skill.version for skill in enabled} == {"1.1.0"}


async def test_admin_can_list_and_disable_skill(
    api_client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    write_manifest(tmp_path)
    admin = await register_user(
        api_client,
        email=f"skill-admin-{uuid4().hex}@example.com",
    )
    await promote_admin(str(admin["user"]["id"]))
    token = str(admin["access_token"])
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        skills_root=tmp_path,
    )
    try:
        listed = await api_client.get(
            "/api/v1/admin/skills",
            headers=auth_headers(token),
        )
        assert listed.status_code == 200, listed.text
        assert listed.json()["items"][0]["name"] == "route-optimization"
        assert listed.json()["items"][0]["enabled"] is True

        disabled = await api_client.post(
            "/api/v1/admin/skills/route-optimization/toggle",
            headers=auth_headers(token),
            json={"enabled": False, "reason": "maintenance"},
        )
        assert disabled.status_code == 200, disabled.text
        assert disabled.json()["enabled"] is False

        relisted = await api_client.get(
            "/api/v1/admin/skills",
            headers=auth_headers(token),
        )
        assert relisted.json()["items"][0]["enabled"] is False

        audits = await api_client.get(
            "/api/v1/admin/audit-logs",
            headers=auth_headers(token),
        )
        assert audits.status_code == 200
        assert audits.json()["items"][0]["action"] == "skill.toggle"
        assert audits.json()["items"][0]["target_id"] == "route-optimization"
    finally:
        app.dependency_overrides.pop(get_settings, None)


async def test_admin_skill_toggle_rejects_unknown_skill(
    api_client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    admin = await register_user(
        api_client,
        email=f"skill-missing-{uuid4().hex}@example.com",
    )
    await promote_admin(str(admin["user"]["id"]))
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        skills_root=tmp_path,
    )
    try:
        response = await api_client.post(
            "/api/v1/admin/skills/missing-skill/toggle",
            headers=auth_headers(str(admin["access_token"])),
            json={"enabled": False},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "skill_not_found"


async def test_admin_skill_list_fails_closed_for_invalid_manifest(
    api_client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    write_manifest(tmp_path, extra_yaml="script: unsafe\n")
    admin = await register_user(
        api_client,
        email=f"skill-invalid-{uuid4().hex}@example.com",
    )
    await promote_admin(str(admin["user"]["id"]))
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        skills_root=tmp_path,
    )
    try:
        response = await api_client.get(
            "/api/v1/admin/skills",
            headers=auth_headers(str(admin["access_token"])),
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "skill_registry_invalid"
