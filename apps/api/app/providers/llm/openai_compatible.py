# 文件说明：LLM Provider：openai_compatible。
import asyncio
import json
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import SecretStr

from app.providers.llm.base import (
    LlmInvalidResponseError,
    LlmProviderError,
    LlmRateLimitError,
    LlmRequest,
    LlmResponse,
    LlmSourceCitation,
    LlmTimeoutError,
    LlmUsage,
    ToolCall,
    ToolCallingRequest,
    ToolCallingResponse,
)


class OpenAICompatibleLlmProvider:
    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        proxy_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.model_name = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._client = client
        self._proxy_url = proxy_url

    async def generate(self, request: LlmRequest) -> LlmResponse:
        if self._client is not None:
            return await self._generate_with_client(self._client, request)
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            proxy=self._proxy_url,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            return await self._generate_with_client(client, request)

    async def generate_with_tools(
        self,
        request: ToolCallingRequest,
    ) -> ToolCallingResponse:
        if self._client is not None:
            return await self._generate_tools_with_client(self._client, request)
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            proxy=self._proxy_url,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            return await self._generate_tools_with_client(client, request)

    async def _generate_tools_with_client(
        self,
        client: httpx.AsyncClient,
        request: ToolCallingRequest,
    ) -> ToolCallingResponse:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "tools": [tool.to_openai() for tool in request.tools],
            "tool_choice": "auto",
            "temperature": 0,
            "max_tokens": request.max_tokens,
            "thinking": {"type": "disabled"},
            "stream": False,
        }
        started = time.perf_counter()
        response = await self._post_with_retries(client, payload)
        latency_ms = max(1, int((time.perf_counter() - started) * 1_000))
        return self._parse_tool_response(response, latency_ms)

    async def _generate_with_client(
        self,
        client: httpx.AsyncClient,
        request: LlmRequest,
    ) -> LlmResponse:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {
                    "role": "user",
                    "content": self._user_content(
                        request.user_prompt,
                        request.image_data_urls,
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": request.max_tokens,
            "thinking": {
                "type": "enabled" if request.thinking_enabled else "disabled"
            },
            "stream": False,
        }
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}
        web_tools: list[dict[str, str]] = []
        # DeepSeek Web Tools 是服务端工具，不能与自定义 Function Tools 混用。
        if request.web_search:
            web_tools.append({"type": "deepseek_web_search"})
        if request.read_url:
            web_tools.append({"type": "deepseek_read_url"})
        if web_tools:
            payload["tools"] = web_tools
            payload["tool_choice"] = "auto"
        started = time.perf_counter()
        response = await self._post_with_retries(client, payload)
        latency_ms = max(1, int((time.perf_counter() - started) * 1_000))
        return self._parse_response(response, latency_ms)

    @staticmethod
    def _user_content(
        text: str,
        image_data_urls: tuple[str, ...],
    ) -> str | list[dict[str, object]]:
        if not image_data_urls:
            return text
        content: list[dict[str, object]] = [
            {"type": "text", "text": text},
        ]
        content.extend(
            {
                "type": "image_url",
                "image_url": {"url": image_url},
            }
            for image_url in image_data_urls
        )
        return content

    async def _post_with_retries(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, object],
    ) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        for attempt in range(self._max_retries + 1):
            try:
                response = await client.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
                    continue
                raise LlmTimeoutError("LLM request timed out") from exc
            except httpx.HTTPError as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
                    continue
                raise LlmProviderError("LLM transport failed") from exc

            if response.status_code == 429:
                if attempt < self._max_retries:
                    await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
                    continue
                raise LlmRateLimitError("LLM provider rate limited the request")
            if response.status_code >= 500:
                if attempt < self._max_retries:
                    await asyncio.sleep(min(0.25 * (2**attempt), 2.0))
                    continue
                raise LlmProviderError("LLM provider returned a server error")
            if response.status_code >= 400:
                raise LlmProviderError(_http_error_message(response))
            return response
        raise LlmProviderError("LLM request failed")

    def _parse_response(
        self,
        response: httpx.Response,
        latency_ms: int,
    ) -> LlmResponse:
        try:
            payload = response.json()
        except ValueError as exc:
            raise LlmInvalidResponseError("LLM response was not JSON") from exc
        if not isinstance(payload, dict):
            raise LlmInvalidResponseError("LLM response must be a JSON object")

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LlmInvalidResponseError("LLM response did not include choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise LlmInvalidResponseError("LLM choice must be an object")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise LlmInvalidResponseError("LLM response did not include a message")
        finish_reason = str(first_choice.get("finish_reason") or "unknown")
        usage_payload = payload.get("usage")
        usage = usage_payload if isinstance(usage_payload, dict) else {}
        content, sources = _content_and_sources(message)
        if not isinstance(content, str) or not content.strip():
            completion_tokens = _token_count(usage.get("completion_tokens"))
            raise LlmInvalidResponseError(
                "LLM response did not include text content "
                f"(finish_reason={finish_reason}, "
                f"completion_tokens={completion_tokens})"
            )
        return LlmResponse(
            content=content,
            usage=LlmUsage(
                input_tokens=_token_count(usage.get("prompt_tokens")),
                output_tokens=_token_count(usage.get("completion_tokens")),
                latency_ms=latency_ms,
                model_name=str(payload.get("model") or self.model_name),
                search_count=_usage_server_tool_count(usage, "tool_search"),
                fetch_count=_usage_server_tool_count(usage, "tool_fetch"),
            ),
            sources=tuple(sources),
        )

    def _parse_tool_response(
        self,
        response: httpx.Response,
        latency_ms: int,
    ) -> ToolCallingResponse:
        try:
            payload = response.json()
        except ValueError as exc:
            raise LlmInvalidResponseError("LLM response was not JSON") from exc
        if not isinstance(payload, dict):
            raise LlmInvalidResponseError("LLM response must be a JSON object")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LlmInvalidResponseError("LLM response did not include choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise LlmInvalidResponseError("LLM choice must be an object")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise LlmInvalidResponseError("LLM response did not include a message")
        raw_calls = message.get("tool_calls")
        calls: list[ToolCall] = []
        if isinstance(raw_calls, list):
            for raw_call in raw_calls:
                calls.append(self._parse_tool_call(raw_call))
        content = message.get("content")
        if (
            (not isinstance(content, str) or not content.strip())
            and not calls
        ):
            raise LlmInvalidResponseError("LLM response did not include content or tool calls")
        usage_payload = payload.get("usage")
        usage = usage_payload if isinstance(usage_payload, dict) else {}
        return ToolCallingResponse(
            content=content if isinstance(content, str) else None,
            tool_calls=calls,
            usage=LlmUsage(
                input_tokens=_token_count(usage.get("prompt_tokens")),
                output_tokens=_token_count(usage.get("completion_tokens")),
                latency_ms=latency_ms,
                model_name=str(payload.get("model") or self.model_name),
                search_count=_usage_server_tool_count(usage, "tool_search"),
                fetch_count=_usage_server_tool_count(usage, "tool_fetch"),
            ),
        )

    @staticmethod
    def _parse_tool_call(raw_call: object) -> ToolCall:
        if not isinstance(raw_call, dict):
            raise LlmInvalidResponseError("LLM tool call must be an object")
        function = raw_call.get("function")
        if not isinstance(function, dict):
            raise LlmInvalidResponseError("LLM tool call did not include a function")
        raw_arguments = function.get("arguments")
        if not isinstance(raw_arguments, str):
            raise LlmInvalidResponseError("LLM tool call arguments must be JSON text")
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise LlmInvalidResponseError("LLM tool call arguments were invalid JSON") from exc
        if not isinstance(arguments, dict):
            raise LlmInvalidResponseError("LLM tool call arguments must be an object")
        return ToolCall(
            id=str(raw_call.get("id") or ""),
            name=str(function.get("name") or ""),
            arguments=arguments,
        )


def _token_count(value: Any) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _http_error_message(response: httpx.Response) -> str:
    error_code: object = None
    error_message: object = None
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            error_code = error.get("code")
            error_message = error.get("message")
        elif isinstance(error, str):
            error_message = error
    detail = " ".join(
        str(part).strip()
        for part in (error_code, error_message)
        if part is not None and str(part).strip()
    )
    detail = " ".join(detail.split())[:500] or response.reason_phrase
    return f"LLM provider rejected the request (HTTP {response.status_code}): {detail}"


def _content_and_sources(
    message: dict[str, object],
) -> tuple[str | None, list[LlmSourceCitation]]:
    """从 Provider 输出中提取文本，并生成净化、去重后的 citations。"""
    sources: list[LlmSourceCitation] = []
    raw_content = message.get("content")
    content = raw_content if isinstance(raw_content, str) else None
    if isinstance(raw_content, list):
        text_parts: list[str] = []
        for block in raw_content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str):
                text_parts.append(text)
            _append_citations(sources, block.get("citations"))
        content = "".join(text_parts) or None
    _append_citations(sources, message.get("annotations"))
    return content, _dedupe_sources(sources)


def _append_citations(
    target: list[LlmSourceCitation],
    raw_citations: object,
) -> None:
    if not isinstance(raw_citations, list):
        return
    for item in raw_citations:
        if not isinstance(item, dict):
            continue
        citation = item.get("url_citation")
        payload = citation if isinstance(citation, dict) else item
        url = _safe_http_url(payload.get("url"))
        if url is None:
            continue
        target.append(
            LlmSourceCitation(
                url=url,
                title=_optional_text(payload.get("title")),
                cited_text=_optional_text(payload.get("cited_text")),
                published_at=_optional_text(payload.get("published_at")),
            )
        )


def _dedupe_sources(
    sources: list[LlmSourceCitation],
) -> list[LlmSourceCitation]:
    deduped: dict[str, LlmSourceCitation] = {}
    for source in sources:
        deduped.setdefault(source.url, source)
    return list(deduped.values())


def _safe_http_url(value: object) -> str | None:
    """模型提供的来源只允许 HTTP(S)，避免不安全链接进入前端。"""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return normalized


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _usage_server_tool_count(usage: dict[str, object], key: str) -> int:
    server_tool_use = usage.get("server_tool_use")
    if isinstance(server_tool_use, dict):
        return _token_count(server_tool_use.get(key))
    return _token_count(usage.get(key))
