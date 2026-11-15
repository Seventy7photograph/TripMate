# 文件说明：FastAPI 路由：chat。
"""旅行对话 API：先识别意图，再进入规划或 Web 研究链路。"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.agents.travel_chat import TravelChatAgent
from app.api.deps import (
    CurrentUserDep,
    SessionDep,
    SettingsDep,
    rate_limit,
    require_feature,
)
from app.api.v1.uploads import UploadServiceDep, upload_error
from app.providers.llm.base import (
    LlmProviderError,
    LlmRateLimitError,
    LlmTimeoutError,
)
from app.providers.llm.factory import LlmConfigurationError, build_llm_provider
from app.schemas.chat import TravelChatRequest, TravelChatResponse
from app.services.conversation_service import ConversationNotFoundError
from app.services.cost_guard import CostLimitExceeded, hash_client_ip
from app.services.feature_service import FeatureFlagService
from app.services.model_config_service import ModelConfigError, ModelConfigService
from app.services.travel_chat_service import TravelChatService
from app.services.upload_service import UploadError
from app.skills.runtime import build_skill_runtime
from app.skills.state_service import SkillStateService

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
) -> AsyncIterator[TravelChatService]:
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

    runtime = await build_skill_runtime(
        session=session,
        settings=stage_settings,
        owner_id=current_user.id,
    )
    feature_service = FeatureFlagService(session)
    skills_enabled = await feature_service.is_enabled(
        "agent_skills_enabled"
    )
    router_enabled = await feature_service.is_enabled(
        "agent_skill_router_enabled"
    )
    available_skills = (
        await SkillStateService(session).enabled_manifests(
            runtime.registry
        )
        if skills_enabled and router_enabled
        else []
    )
    try:
        agent = TravelChatAgent(
            provider=provider,
            available_skills=available_skills,
            tool_registry=runtime.tools,
            tool_context=runtime.tool_context,
            skill_handlers=runtime.handlers,
        )
        yield TravelChatService(session, agent, settings)
    finally:
        await runtime.close()


TravelChatServiceDep = Annotated[
    TravelChatService,
    Depends(get_travel_chat_service),
]


@router.post("/respond", response_model=TravelChatResponse)
async def respond_to_travel_chat(
    payload: TravelChatRequest,
    request: Request,
    current_user: CurrentUserDep,
    settings: SettingsDep,
    _chat_feature: ChatFeatureDep,
    _llm_feature: LlmFeatureDep,
    _rate_limit: ChatRateLimitDep,
    service: TravelChatServiceDep,
    upload_service: UploadServiceDep,
) -> TravelChatResponse:
    """接收文本或隔离附件，并返回完成路由的旅行响应。"""
    request_ip_hash = (
        hash_client_ip(
            request.client.host,
            settings.jwt_secret.get_secret_value(),
        )
        if request.client is not None
        else None
    )
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
            attachment_ids=payload.attachment_ids,
            conversation_id=payload.conversation_id,
            client_today=payload.client_today,
            request_ip_hash=request_ip_hash,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        ) from exc
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
