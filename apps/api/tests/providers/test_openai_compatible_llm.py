# 文件说明：后端自动化测试：test_openai_compatible_llm。
import json

import httpx
import pytest
from pydantic import SecretStr

from app.providers.llm.base import (
    LlmInvalidResponseError,
    LlmProviderError,
    LlmRateLimitError,
    LlmRequest,
    LlmTimeoutError,
    ToolCallingRequest,
    ToolDefinition,
)
from app.providers.llm.openai_compatible import OpenAICompatibleLlmProvider


def llm_request() -> LlmRequest:
    return LlmRequest(
        system_prompt="Return JSON only.",
        user_prompt="Parse: 2 people to Chongqing.",
        user_text="2 people to Chongqing",
        response_schema={"type": "object"},
    )


def provider(client: httpx.AsyncClient) -> OpenAICompatibleLlmProvider:
    return OpenAICompatibleLlmProvider(
        api_key=SecretStr("test-secret"),
        base_url="https://llm.example/v1",
        model="test-model",
        timeout_seconds=3,
        max_retries=0,
        client=client,
    )


async def test_openai_compatible_provider_uses_structured_json_request() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://llm.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-secret"
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert body["response_format"] == {"type": "json_object"}
        assert body["temperature"] == 0
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"
        return httpx.Response(
            200,
            json={
                "model": "test-model-2026",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"destination": "重庆"}),
                        }
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await provider(client).generate(llm_request())

    assert json.loads(response.content) == {"destination": "重庆"}
    assert response.usage.input_tokens == 12
    assert response.usage.output_tokens == 7
    assert response.usage.model_name == "test-model-2026"


async def test_openai_compatible_provider_maps_rate_limit() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LlmRateLimitError):
            await provider(client).generate(llm_request())


async def test_openai_compatible_provider_reports_safe_http_error_detail() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": "invalid_request_error",
                    "message": "response_format is not supported by this model",
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LlmProviderError) as raised:
            await provider(client).generate(llm_request())

    message = str(raised.value)
    assert "HTTP 400" in message
    assert "invalid_request_error" in message
    assert "response_format is not supported" in message
    assert "test-secret" not in message


async def test_openai_compatible_provider_maps_timeout() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LlmTimeoutError):
            await provider(client).generate(llm_request())


async def test_openai_compatible_provider_rejects_missing_content() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {
                            "content": None,
                            "reasoning_content": "model reasoning",
                        },
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 5_000},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LlmInvalidResponseError) as raised:
            await provider(client).generate(llm_request())

    assert "finish_reason=length" in str(raised.value)
    assert "completion_tokens=5000" in str(raised.value)


async def test_openai_compatible_provider_executes_function_call_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["tools"][0]["function"]["name"] == "search_places"
        assert body["tool_choice"] == "auto"
        return httpx.Response(
            200,
            json={
                "model": "test-model-2026",
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_places",
                                        "arguments": json.dumps(
                                            {"keyword": "洪崖洞", "limit": 3}
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 9, "completion_tokens": 4},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await provider(client).generate_with_tools(
            ToolCallingRequest(
                system_prompt="Choose tools.",
                user_prompt="Find places.",
                user_text="Find places.",
                tools=[
                    ToolDefinition(
                        name="search_places",
                        description="Search places",
                        parameters={"type": "object"},
                    )
                ],
            )
        )

    assert response.tool_calls[0].name == "search_places"
    assert response.tool_calls[0].arguments == {"keyword": "洪崖洞", "limit": 3}
    assert response.usage.input_tokens == 9


async def test_openai_compatible_provider_supports_web_tools_and_citations() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "deepseek-flash"
        assert body["thinking"] == {"type": "enabled"}
        assert body["max_tokens"] == 24_000
        assert "response_format" not in body
        assert body["tools"] == [
            {"type": "deepseek_web_search"},
            {"type": "deepseek_read_url"},
        ]
        assert body["tool_choice"] == "auto"
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": "泉州开元寺适合古建爱好者。",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url_citation": {
                                        "url": "https://example.com/quanzhou",
                                        "title": "泉州文旅",
                                        "start_index": 0,
                                        "end_index": 10,
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 30,
                    "server_tool_use": {
                        "tool_search": 1,
                        "tool_fetch": 2,
                    },
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        flash_provider = OpenAICompatibleLlmProvider(
            api_key=SecretStr("test-secret"),
            base_url="https://llm.example/v1",
            model="deepseek-flash",
            timeout_seconds=3,
            max_retries=0,
            client=client,
        )
        response = await flash_provider.generate(
            LlmRequest(
                system_prompt="Only answer travel questions.",
                user_prompt="泉州古建怎么玩？",
                user_text="泉州古建怎么玩？",
                response_schema={"type": "object"},
                json_mode=False,
                web_search=True,
                read_url=True,
                thinking_enabled=True,
                max_tokens=24_000,
            )
        )

    assert response.content == "泉州开元寺适合古建爱好者。"
    assert response.sources[0].url == "https://example.com/quanzhou"
    assert response.sources[0].title == "泉州文旅"
    assert response.usage.search_count == 1
    assert response.usage.fetch_count == 2


async def test_live_profile_without_key_returns_service_unavailable(
    api_client: httpx.AsyncClient,
) -> None:
    from app.api.deps import get_settings
    from app.core.config import Settings
    from app.main import app
    from tests.test_auth import auth_headers, register_user

    registration = await register_user(api_client)
    token = str(registration["access_token"])

    def live_settings() -> Settings:
        return Settings(
            app_env="test",
            provider_profile="live",
            llm_api_key=None,
            llm_model="",
        )

    app.dependency_overrides[get_settings] = live_settings
    try:
        response = await api_client.post(
            "/api/v1/briefs/parse",
            headers=auth_headers(token),
            json={"text": "2026年12月1日到12月3日，2个人去重庆，预算5000元。"},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "llm_not_configured"
