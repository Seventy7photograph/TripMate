# 文件说明：后端自动化测试：test_multimodal_request。
import json

import httpx
from pydantic import SecretStr

from app.providers.llm.base import LlmRequest
from app.providers.llm.openai_compatible import OpenAICompatibleLlmProvider


async def test_openai_compatible_sends_image_content_parts() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "vision-model",
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"destination":"重庆","origin":null,'
                                '"start_date":null,"end_date":null,'
                                '"party_size":null,"budget_minor":null,'
                                '"currency":"CNY","interests":[],'
                                '"pace":"balanced",'
                                '"transport_preferences":[],'
                                '"lodging_preferences":[],"must_visit":[],'
                                '"avoid":[],"constraints":[]}'
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        provider = OpenAICompatibleLlmProvider(
            api_key=SecretStr("secret"),
            base_url="https://api.example.test/v1",
            model="vision-model",
            timeout_seconds=5,
            max_retries=0,
            client=client,
        )
        await provider.generate(
            LlmRequest(
                system_prompt="system",
                user_prompt="识别附件",
                user_text="附件",
                response_schema={},
                image_data_urls=("data:image/png;base64,AAAA",),
            )
        )

    messages = captured["messages"]
    assert isinstance(messages, list)
    content = messages[1]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png")
