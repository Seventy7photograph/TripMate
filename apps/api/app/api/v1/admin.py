# 文件说明：FastAPI 路由：admin。
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import AdminUserDep, SessionDep, SettingsDep
from app.schemas.admin import (
    AdminAgentRunListResponse,
    AdminAuditLogListResponse,
    AdminCostSummaryResponse,
    AdminMcpConnectorListResponse,
    AdminMcpConnectorResponse,
    AdminProviderListResponse,
    AdminToolHealthListResponse,
    FeatureFlagListResponse,
    FeatureFlagResponse,
    FeatureToggleRequest,
    McpConnectorToggleRequest,
    ModelConfigListResponse,
    ModelConfigResponse,
    ModelConfigUpdateRequest,
)
from app.schemas.skill import (
    SkillListResponse,
    SkillResponse,
    SkillToggleRequest,
)
from app.services.feature_service import (
    FeatureFlagService,
    FeatureNotFoundError,
)
from app.services.mcp_connector_service import (
    McpConnectorNotFoundError,
    McpConnectorService,
)
from app.services.model_config_service import (
    ModelConfigError,
    ModelConfigService,
    ModelStageNotFoundError,
)
from app.services.observability_service import ObservabilityService
from app.skills.manifest import SkillManifestError
from app.skills.registry import (
    SkillNotFoundError,
    SkillRegistry,
    load_configured_registry,
)
from app.skills.state_service import SkillStateService

router = APIRouter(prefix="/admin", tags=["admin"])


def get_observability_service(
    session: SessionDep,
    settings: SettingsDep,
) -> ObservabilityService:
    return ObservabilityService(session, settings)


ObservabilityServiceDep = Annotated[
    ObservabilityService,
    Depends(get_observability_service),
]


def get_feature_service(session: SessionDep) -> FeatureFlagService:
    return FeatureFlagService(session)


FeatureServiceDep = Annotated[FeatureFlagService, Depends(get_feature_service)]


def get_model_config_service(
    session: SessionDep,
    settings: SettingsDep,
) -> ModelConfigService:
    return ModelConfigService(session, settings)


ModelConfigServiceDep = Annotated[
    ModelConfigService,
    Depends(get_model_config_service),
]


def get_skill_registry(settings: SettingsDep) -> SkillRegistry:
    try:
        return load_configured_registry(settings)
    except SkillManifestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "skill_registry_invalid",
                "message": "Skill registry configuration is invalid",
            },
        ) from exc


SkillRegistryDep = Annotated[SkillRegistry, Depends(get_skill_registry)]


def get_skill_state_service(session: SessionDep) -> SkillStateService:
    return SkillStateService(session)


SkillStateServiceDep = Annotated[
    SkillStateService,
    Depends(get_skill_state_service),
]


def get_mcp_connector_service(
    session: SessionDep,
    settings: SettingsDep,
) -> McpConnectorService:
    return McpConnectorService(session, settings)


McpConnectorServiceDep = Annotated[
    McpConnectorService,
    Depends(get_mcp_connector_service),
]


@router.get("/agent-runs", response_model=AdminAgentRunListResponse)
async def list_agent_runs(
    _: AdminUserDep,
    service: ObservabilityServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    purpose: Annotated[str | None, Query(max_length=32)] = None,
    provider: Annotated[str | None, Query(max_length=40)] = None,
) -> AdminAgentRunListResponse:
    return await service.list_agent_runs(
        limit=limit,
        offset=offset,
        status=status_filter,
        purpose=purpose,
        provider=provider,
    )


@router.get("/costs", response_model=AdminCostSummaryResponse)
async def get_costs(
    _: AdminUserDep,
    service: ObservabilityServiceDep,
    days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> AdminCostSummaryResponse:
    return await service.cost_summary(days=days)


@router.get("/providers", response_model=AdminProviderListResponse)
async def list_providers(
    _: AdminUserDep,
    service: ObservabilityServiceDep,
) -> AdminProviderListResponse:
    return await service.providers()


@router.get(
    "/tool-health",
    response_model=AdminToolHealthListResponse,
)
async def list_tool_health(
    _: AdminUserDep,
    service: ObservabilityServiceDep,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> AdminToolHealthListResponse:
    return await service.tool_health(hours=hours)


@router.get(
    "/mcp-connectors",
    response_model=AdminMcpConnectorListResponse,
)
async def list_mcp_connectors(
    _: AdminUserDep,
    service: McpConnectorServiceDep,
) -> AdminMcpConnectorListResponse:
    return AdminMcpConnectorListResponse(
        items=[
            AdminMcpConnectorResponse.model_validate(state)
            for state in await service.list_connectors()
        ]
    )


@router.post(
    "/mcp-connectors/{connector_id}/toggle",
    response_model=AdminMcpConnectorResponse,
)
async def toggle_mcp_connector(
    connector_id: str,
    payload: McpConnectorToggleRequest,
    current_user: AdminUserDep,
    service: McpConnectorServiceDep,
) -> AdminMcpConnectorResponse:
    try:
        state = await service.set_enabled(
            connector_id=connector_id,
            enabled=payload.enabled,
            actor_id=current_user.id,
            reason=payload.reason,
        )
    except McpConnectorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "mcp_connector_not_found",
                "message": "Unknown MCP connector",
            },
        ) from exc
    return AdminMcpConnectorResponse.model_validate(state)


@router.get("/features", response_model=FeatureFlagListResponse)
async def list_features(
    _: AdminUserDep,
    service: FeatureServiceDep,
) -> FeatureFlagListResponse:
    flags = await service.list_flags()
    return FeatureFlagListResponse(
        items=[
            FeatureFlagResponse(
                key=flag.key,  # type: ignore[arg-type]
                label=flag.label,
                description=flag.description,
                enabled=flag.enabled,
                updated_by=flag.updated_by,
                updated_at=flag.updated_at,
            )
            for flag in flags
        ]
    )


@router.post(
    "/features/{feature}/toggle",
    response_model=FeatureFlagResponse,
)
async def toggle_feature(
    feature: str,
    payload: FeatureToggleRequest,
    current_user: AdminUserDep,
    service: FeatureServiceDep,
) -> FeatureFlagResponse:
    try:
        flag = await service.toggle(
            key=feature,
            enabled=payload.enabled,
            actor_id=current_user.id,
            reason=payload.reason,
        )
    except FeatureNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "feature_not_found",
                "message": "Unknown feature flag",
            },
        ) from exc
    return FeatureFlagResponse(
        key=flag.key,  # type: ignore[arg-type]
        label=flag.label,
        description=flag.description,
        enabled=flag.enabled,
        updated_by=flag.updated_by,
        updated_at=flag.updated_at,
    )


@router.get("/audit-logs", response_model=AdminAuditLogListResponse)
async def list_audit_logs(
    _: AdminUserDep,
    service: ObservabilityServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminAuditLogListResponse:
    return await service.audit_logs(limit=limit, offset=offset)


@router.get("/model-configs", response_model=ModelConfigListResponse)
async def list_model_configs(
    _: AdminUserDep,
    service: ModelConfigServiceDep,
) -> ModelConfigListResponse:
    return ModelConfigListResponse(items=await service.list_configs())


@router.patch(
    "/model-configs/{stage}",
    response_model=ModelConfigResponse,
)
async def update_model_config(
    stage: str,
    payload: ModelConfigUpdateRequest,
    current_user: AdminUserDep,
    service: ModelConfigServiceDep,
) -> ModelConfigResponse:
    try:
        return await service.update(
            stage=stage,
            payload=payload,
            actor_id=current_user.id,
        )
    except ModelStageNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "model_stage_not_found",
                "message": "Unknown model stage",
            },
        ) from exc
    except ModelConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "unsafe_model_url",
                "message": str(exc),
            },
        ) from exc


@router.get("/skills", response_model=SkillListResponse)
async def list_skills(
    _: AdminUserDep,
    registry: SkillRegistryDep,
    service: SkillStateServiceDep,
) -> SkillListResponse:
    views = await service.skill_views(registry)
    return SkillListResponse(
        items=[SkillResponse.model_validate(view) for view in views]
    )


@router.post(
    "/skills/{skill_name}/toggle",
    response_model=SkillResponse,
)
async def toggle_skill(
    skill_name: str,
    payload: SkillToggleRequest,
    current_user: AdminUserDep,
    registry: SkillRegistryDep,
    service: SkillStateServiceDep,
) -> SkillResponse:
    try:
        manifest = registry.get(skill_name)
    except SkillNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "skill_not_found",
                "message": "Unknown skill",
            },
        ) from exc
    await service.set_enabled(
        skill_name=manifest.name,
        version=manifest.version,
        enabled=payload.enabled,
        actor_id=current_user.id,
        reason=payload.reason,
        default_enabled=manifest.status == "active",
    )
    views = await service.skill_views(registry)
    view = next(item for item in views if item.name == skill_name)
    return SkillResponse.model_validate(view)
