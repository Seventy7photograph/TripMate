# 文件说明：FastAPI 路由：briefs。
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.requirement_parser import RequirementParseError
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
from app.schemas.requirement import RequirementParseRequest, RequirementParseResponse
from app.services.brief_service import BriefService
from app.services.model_config_service import ModelConfigError, ModelConfigService
from app.services.upload_service import UploadError

router = APIRouter(prefix="/briefs", tags=["briefs"])


async def get_brief_service(
    session: SessionDep,
    settings: SettingsDep,
) -> BriefService:
    try:
        stage_settings = await ModelConfigService(session, settings).settings_for(
            "brief_parse"
        )
        provider = build_llm_provider(stage_settings)
    except (LlmConfigurationError, ModelConfigError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "llm_not_configured",
                "message": "真实模型尚未配置，请联系管理员",
            },
        ) from exc
    return BriefService(
        session,
        provider,
        max_repairs=stage_settings.llm_max_repairs,
    )


BriefServiceDep = Annotated[BriefService, Depends(get_brief_service)]
BriefFeatureDep = Annotated[None, Depends(require_feature("brief_parsing"))]
LlmFeatureDep = Annotated[None, Depends(require_feature("llm_provider"))]
BriefRateLimitDep = Annotated[
    None,
    Depends(
        rate_limit(
            scope="brief_parse",
            limit_attribute="rate_limit_brief_parse_per_minute",
        )
    ),
]


@router.post("/parse", response_model=RequirementParseResponse)
async def parse_requirement(
    payload: RequirementParseRequest,
    current_user: CurrentUserDep,
    _brief_feature: BriefFeatureDep,
    _llm_feature: LlmFeatureDep,
    _rate_limit: BriefRateLimitDep,
    service: BriefServiceDep,
    upload_service: UploadServiceDep,
) -> RequirementParseResponse:
    try:
        upload_context = (
            await upload_service.context_for_message(
                owner_id=current_user.id,
                asset_ids=payload.attachment_ids,
            )
            if payload.attachment_ids
            else None
        )
        result = await service.parse(
            owner_id=current_user.id,
            text=payload.text,
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
                "message": "模型响应超时，请稍后重试",
            },
        ) from exc
    except LlmRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "llm_rate_limited",
                "message": "模型请求过于频繁，请稍后重试",
            },
        ) from exc
    except LlmProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "llm_provider_error",
                "message": "模型服务暂时不可用",
            },
        ) from exc
    except RequirementParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "invalid_llm_output",
                "message": "旅行需求解析失败，请补充信息后重试",
            },
        ) from exc
    except UploadError as exc:
        raise upload_error(exc) from exc
    return result.response
