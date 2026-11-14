# 文件说明：LLM Provider：factory。
from pydantic import SecretStr

from app.core.config import Settings
from app.providers.llm.base import StructuredLlmProvider
from app.providers.llm.mock import MockLlmProvider
from app.providers.llm.openai_compatible import OpenAICompatibleLlmProvider


class LlmConfigurationError(Exception):
    pass


def build_llm_provider(settings: Settings) -> StructuredLlmProvider:
    if settings.provider_profile == "mock":
        return MockLlmProvider()
    if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value().strip():
        raise LlmConfigurationError("LLM_API_KEY is required for live provider profile")
    if not settings.llm_model.strip():
        raise LlmConfigurationError("LLM_MODEL is required for live provider profile")
    return OpenAICompatibleLlmProvider(
        api_key=SecretStr(settings.llm_api_key.get_secret_value()),
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        proxy_url=(
            settings.outbound_proxy_url.get_secret_value()
            if settings.outbound_proxy_url is not None
            else None
        ),
    )
