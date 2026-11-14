# 文件说明：FastAPI 路由：planning。
import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    CurrentUserDep,
    SessionDep,
    SettingsDep,
    rate_limit,
    require_feature,
)
from app.graph.travel_graph import create_travel_graph
from app.providers.base import ProviderConfigurationError
from app.providers.llm.factory import LlmConfigurationError
from app.schemas.ai import (
    PlanningJobCreateRequest,
    PlanningJobResponse,
    PlanningJobStartResponse,
)
from app.services.cost_guard import CostLimitExceeded, hash_client_ip
from app.services.feature_service import FeatureDisabledError
from app.services.model_config_service import ModelConfigError, ModelConfigService
from app.services.planning_service import (
    AgentRunView,
    PlanningService,
    PlanningTripNotFoundError,
)
from app.services.version_service import VersionConflictError

router = APIRouter(tags=["planning"])


async def get_planning_service(
    session: SessionDep,
    settings: SettingsDep,
) -> PlanningService:
    try:
        model_configs = ModelConfigService(session, settings)
        research_settings = await model_configs.settings_for("research_planner")
        composer_settings = await model_configs.settings_for("itinerary_composer")
        graph = create_travel_graph(
            settings,
            research_settings=research_settings,
            composer_settings=composer_settings,
        )
        return PlanningService(session, settings, graph=graph)
    except (LlmConfigurationError, ModelConfigError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "llm_not_configured",
                "message": "真实模型尚未配置，请联系管理员",
            },
        ) from exc
    except ProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "planning_provider_not_configured",
                "message": "地图 Provider 尚未配置，请联系管理员",
            },
        ) from exc


PlanningServiceDep = Annotated[PlanningService, Depends(get_planning_service)]
AiPlanningFeatureDep = Annotated[
    None,
    Depends(require_feature("ai_planning")),
]
LlmFeatureDep = Annotated[None, Depends(require_feature("llm_provider"))]
MapFeatureDep = Annotated[None, Depends(require_feature("map_provider"))]
PlanningRateLimitDep = Annotated[
    None,
    Depends(
        rate_limit(
            scope="planning",
            limit_attribute="rate_limit_planning_per_minute",
        )
    ),
]


def not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Planning job not found",
    )


def version_conflict(exc: VersionConflictError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "version_conflict",
            "message": "Trip was updated by another session",
            "current_version": exc.current_version,
        },
    )


@router.post(
    "/trips/{trip_id}/plan",
    response_model=PlanningJobStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_planning(
    trip_id: UUID,
    payload: PlanningJobCreateRequest,
    request: Request,
    current_user: CurrentUserDep,
    settings: SettingsDep,
    _ai_feature: AiPlanningFeatureDep,
    _llm_feature: LlmFeatureDep,
    _map_feature: MapFeatureDep,
    _rate_limit: PlanningRateLimitDep,
    service: PlanningServiceDep,
) -> PlanningJobStartResponse:
    request_ip_hash = (
        hash_client_ip(
            request.client.host,
            settings.jwt_secret.get_secret_value(),
        )
        if request.client is not None
        else None
    )
    try:
        job = await service.start(
            owner_id=current_user.id,
            trip_id=trip_id,
            expected_version=payload.expected_version,
            apply_to_itinerary=payload.apply_to_itinerary,
            request_ip_hash=request_ip_hash,
        )
    except VersionConflictError as exc:
        raise version_conflict(exc) from exc
    except PlanningTripNotFoundError as exc:
        raise not_found() from exc
    except FeatureDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "feature_disabled",
                "feature": exc.key,
                "message": "该功能已由管理员暂时关闭",
            },
        ) from exc
    except CostLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "cost_limit_exceeded",
                "scope": exc.scope,
                "limit_minor": exc.limit_minor,
                "spent_minor": exc.spent_minor,
                "message": "今日成本额度已达到上限",
            },
        ) from exc
    return PlanningJobStartResponse(
        job_id=job.id,
        status=job.status,  # type: ignore[arg-type]
    )


@router.get("/jobs/{job_id}", response_model=PlanningJobResponse)
async def get_planning_job(
    job_id: UUID,
    current_user: CurrentUserDep,
    service: PlanningServiceDep,
) -> PlanningJobResponse:
    try:
        job = await service.get_job(owner_id=current_user.id, job_id=job_id)
    except PlanningTripNotFoundError as exc:
        raise not_found() from exc
    return PlanningJobResponse.model_validate(job)


@router.get("/jobs/{job_id}/events")
async def get_planning_events(
    job_id: UUID,
    current_user: CurrentUserDep,
    service: PlanningServiceDep,
) -> StreamingResponse:
    try:
        job = await service.get_job(owner_id=current_user.id, job_id=job_id)
    except PlanningTripNotFoundError as exc:
        raise not_found() from exc

    async def stream() -> AsyncIterator[str]:
        last_sequence = 0
        started = time.monotonic()
        while True:
            current = await service.get_job(
                owner_id=current_user.id,
                job_id=job_id,
            )
            for event in current.events:
                raw_sequence = event.get("sequence", 0)
                sequence = raw_sequence if isinstance(raw_sequence, int) else 0
                if sequence <= last_sequence:
                    continue
                last_sequence = sequence
                event_type = str(event["type"])
                yield f"event: {event_type}\n"
                yield (
                    "data: "
                    f"{json.dumps(event, ensure_ascii=False, separators=(',', ':'))}\n\n"
                )
            if current.status in {"completed", "partial", "failed"}:
                break
            if time.monotonic() - started > 300:
                yield "event: error\n"
                yield (
                    'data: {"type":"error","status":"failed",'
                    '"message":"规划事件流超时"}\n\n'
                )
                break
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.6)

    return _sse_response(job, stream())


def _sse_response(job: AgentRunView, stream: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Planning-Status": job.status,
        },
    )
