# 文件说明：LLM Provider：base。
from dataclasses import dataclass, field
from typing import Protocol


class LlmProviderError(Exception):
    """Base error for external model provider failures."""


class LlmTimeoutError(LlmProviderError):
    """Raised when the model provider exceeds its timeout."""


class LlmRateLimitError(LlmProviderError):
    """Raised when the model provider rejects a request due to rate limits."""


class LlmInvalidResponseError(LlmProviderError):
    """Raised when the provider response does not match the transport contract."""


@dataclass(frozen=True, slots=True)
class LlmUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    model_name: str = ""
    estimated_cost_minor: int = 0
    search_count: int = 0
    fetch_count: int = 0

    def __add__(self, other: "LlmUsage") -> "LlmUsage":
        return LlmUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            latency_ms=self.latency_ms + other.latency_ms,
            model_name=other.model_name or self.model_name,
            estimated_cost_minor=self.estimated_cost_minor + other.estimated_cost_minor,
            search_count=self.search_count + other.search_count,
            fetch_count=self.fetch_count + other.fetch_count,
        )


@dataclass(frozen=True, slots=True)
class LlmSourceCitation:
    url: str
    title: str | None = None
    cited_text: str | None = None
    published_at: str | None = None


@dataclass(frozen=True, slots=True)
class LlmRequest:
    system_prompt: str
    user_prompt: str
    user_text: str
    response_schema: dict[str, object]
    image_data_urls: tuple[str, ...] = ()
    max_tokens: int = 4_000
    metadata: dict[str, str] = field(default_factory=dict)
    json_mode: bool = True
    web_search: bool = False
    read_url: bool = False
    thinking_enabled: bool = False


@dataclass(frozen=True, slots=True)
class LlmResponse:
    content: str
    usage: LlmUsage
    sources: tuple[LlmSourceCitation, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, object]

    def to_openai(self) -> dict[str, object]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolCallingRequest:
    system_prompt: str
    user_prompt: str
    user_text: str
    tools: list[ToolDefinition]
    max_tokens: int = 3_000
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolCallingResponse:
    content: str | None
    tool_calls: list[ToolCall]
    usage: LlmUsage


class StructuredLlmProvider(Protocol):
    provider_name: str
    model_name: str

    async def generate(self, request: LlmRequest) -> LlmResponse: ...


class ToolCallingLlmProvider(Protocol):
    provider_name: str
    model_name: str

    async def generate_with_tools(
        self,
        request: ToolCallingRequest,
    ) -> ToolCallingResponse: ...
