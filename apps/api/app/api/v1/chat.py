# 文件说明：FastAPI 路由：chat。
"""旅行对话 API：先识别意图，再进入规划或 Web 研究链路。"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.travel_chat import TravelChatAgent
from app.api.deps import (
    CurrentUserDep,
    SessionDep,
    SettingsDep,
    rate_limit,
    require_feature,
)
from app.api.v1.uploads import UploadServiceDep, upload_error
from app.evidence.repository import EvidenceRepository
from app.providers.base import NearbyPlaceProvider
from app.providers.llm.base import (
    LlmProviderError,
    LlmRateLimitError,
    LlmTimeoutError,
)
from app.providers.llm.factory import LlmConfigurationError, build_llm_provider
from app.schemas.chat import TravelChatRequest, TravelChatResponse
from app.services.memory_service import MemoryService
from app.services.model_config_service import ModelConfigError, ModelConfigService
from app.services.place_service import PlaceService, create_map_provider
from app.services.travel_chat_service import TravelChatService
from app.services.upload_service import UploadError, UploadService
from app.skills.production import production_skill_handlers
from app.skills.registry import load_configured_registry
from app.skills.state_service import SkillStateService
from app.tools.altitude_tools import AltitudeTool, create_altitude_tool
from app.tools.attachment_tools import AttachmentTool
from app.tools.base import ToolRunner
from app.tools.budget_tools import BudgetTool
from app.tools.context import ToolContext
from app.tools.matrix_tools import MatrixTool
from app.tools.memory_tools import MemoryTool
from app.tools.nearby_tools import NearbyTool
from app.tools.place_detail_tools import PlaceDetailTool
from app.tools.place_fact_tools import PlaceFactTool
from app.tools.place_tools import PlaceTool
from app.tools.registry import ToolRegistry
from app.tools.route_tools import RouteTool
from app.tools.weather_tools import WeatherTool, create_weather_tool

router = APIRouter(prefix="/chat", tags=["chat"])

ChatFeatureDep = Annotated[None, Depends(require_feature("travel_chat"))]
LlmFeatureDep = Annotated[None, Depends(require_feature("llm_provider"))]
ChatRateLimitDep = Annotated[
    None,
    Depends(
        rate_limit(
            scope="travel_chat",
            limit_attribute="rate_limit_travel_chat_per_minute",
        )
    ),
]


async def get_travel_chat_service(
    current_user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
) -> TravelChatService:
    """构建带 owner 边界的 ToolContext，防止 Skill 跨租户访问。"""
    try:
        stage_settings = await ModelConfigService(session, settings).settings_for(
            "travel_chat"
        )
        provider = build_llm_provider(stage_settings)
    except (LlmConfigurationError, ModelConfigError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "llm_not_configured",
                "message": "旅行对话模型尚未配置，请联系管理员",
            },
        ) from exc

    map_provider = create_map_provider(stage_settings)
    tool_context = ToolContext(
        runner=ToolRunner(
            max_calls=settings.planning_max_tool_calls,
            deadline=datetime.now(UTC)
            + timedelta(seconds=settings.planning_timeout_seconds),
        ),
        allowed_tools={
            "search_places",
            "get_route",
            "calculate_budget",
            MemoryTool.name,
            "get_weather",
            "search_nearby_places",
            "get_place_detail",
            "get_place_facts",
            "get_route_matrix",
            "get_altitude",
            "extract_attachment",
        },
        provider_permissions={
            "map",
            "deterministic",
            "memory",
            "weather",
            "attachment",
        },
        owner_id=current_user.id,
        evidence_writer=EvidenceRepository(session),
    )
    place_service = PlaceService(
        session,
        stage_settings,
        provider=map_provider,
    )
    place_tool = PlaceTool(map_provider, tool_context)
    route_tool = RouteTool(map_provider, tool_context)
    budget_tool = BudgetTool(tool_context)
    memory_tool = MemoryTool(MemoryService(session), tool_context)
    weather_tool = create_weather_tool(stage_settings, tool_context)
    nearby_tool = NearbyTool(
        cast(NearbyPlaceProvider, map_provider),
        tool_context,
    )
    place_detail_tool = PlaceDetailTool(place_service, tool_context)
    place_fact_tool = PlaceFactTool(place_service, tool_context)
    matrix_tool = MatrixTool(place_service, route_tool, tool_context)
    altitude_tool = create_altitude_tool(stage_settings, tool_context)
    attachment_tool = AttachmentTool(
        UploadService(session, stage_settings),
        tool_context,
    )
    tools = ToolRegistry()
    tools.register(PlaceTool.spec(), place_tool.invoke)
    tools.register(RouteTool.spec(), route_tool.invoke)
    tools.register(BudgetTool.spec(), budget_tool.invoke)
    tools.register(MemoryTool.spec(), memory_tool.invoke)
    tools.register(WeatherTool.spec(), weather_tool.invoke)
    tools.register(NearbyTool.spec(), nearby_tool.invoke)
    tools.register(PlaceDetailTool.spec(), place_detail_tool.invoke)
    tools.register(PlaceFactTool.spec(), place_fact_tool.invoke)
    tools.register(MatrixTool.spec(), matrix_tool.invoke)
    tools.register(AltitudeTool.spec(), altitude_tool.invoke)
    tools.register(AttachmentTool.spec(), attachment_tool.invoke)
    skill_registry = load_configured_registry(settings)
    available_skills = await SkillStateService(session).enabled_manifests(
        skill_registry
    )
    agent = TravelChatAgent(
        provider=provider,
        available_skills=available_skills,
        tool_registry=tools,
        tool_context=tool_context,
        skill_handlers=production_skill_handlers(tools, tool_context),
    )
    return TravelChatService(session, agent)


TravelChatServiceDep = Annotated[
    TravelChatService,
    Depends(get_travel_chat_service),
]


@router.post("/respond", response_model=TravelChatResponse)
async def respond_to_travel_chat(
    payload: TravelChatRequest,
    current_user: CurrentUserDep,
    _chat_feature: ChatFeatureDep,
    _llm_feature: LlmFeatureDep,
    _rate_limit: ChatRateLimitDep,
    service: TravelChatServiceDep,
    upload_service: UploadServiceDep,
) -> TravelChatResponse:
    """接收文本或隔离附件，并返回完成路由的旅行响应。"""
    try:
        upload_context = (
            await upload_service.context_for_message(
                owner_id=current_user.id,
                asset_ids=payload.attachment_ids,
            )
            if payload.attachment_ids
            else None
        )
        return await service.respond(
            owner_id=current_user.id,
            message=payload.message,
            history=payload.history,
            documents=None if upload_context is None else upload_context.documents,
            image_data_urls=(
                ()
                if upload_context is None
                else tuple(upload_context.image_data_urls)
            ),
        )
    except LlmTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "code": "llm_timeout",
                "message": "旅行对话响应超时，请稍后重试",
            },
        ) from exc
    except LlmRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "llm_rate_limited",
                "message": "旅行对话请求过于频繁，请稍后重试",
            },
        ) from exc
    except LlmProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "llm_provider_error",
                "message": "旅行对话模型暂时不可用",
            },
        ) from exc
    except UploadError as exc:
        raise upload_error(exc) from exc
