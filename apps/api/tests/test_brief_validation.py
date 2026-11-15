# 文件说明：后端自动化测试：test_brief_validation。
from pathlib import Path

import httpx
from sqlalchemy import select

from app.api.deps import get_settings
from app.api.v1.briefs import get_brief_service
from app.main import app
from app.models.agent_run import AgentRun
from app.providers.llm.base import LlmRequest, LlmResponse, LlmTimeoutError, LlmUsage
from app.services.brief_service import BriefService
from tests.test_auth import auth_headers, register_user

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "llm"


class ScriptedProvider:
    provider_name = "scripted"
    model_name = "scripted-model"

    def __init__(self, contents: list[str]) -> None:
        self._contents = contents
        self.requests: list[LlmRequest] = []

    @property
    def call_count(self) -> int:
        return len(self.requests)

    async def generate(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self._contents) - 1)
        return LlmResponse(
            content=self._contents[index],
            usage=LlmUsage(
                input_tokens=10,
                output_tokens=20,
                latency_ms=5,
                model_name=self.model_name,
            ),
        )


class TimeoutProvider:
    provider_name = "timeout"
    model_name = "timeout-model"

    async def generate(self, request: LlmRequest) -> LlmResponse:
        del request
        raise LlmTimeoutError("model request timed out")


def fixture_content(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


async def parse_with_provider(
    api_client: httpx.AsyncClient,
    provider: ScriptedProvider,
) -> httpx.Response:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    async def service_override() -> BriefService:
        return BriefService(
            app.state.test_session,
            provider,
            get_settings(),
        )

    app.dependency_overrides[get_brief_service] = service_override
    try:
        return await api_client.post(
            "/api/v1/briefs/parse",
            headers=auth_headers(token),
            json={"text": "2026年12月1日到12月3日，2个人从上海去重庆，预算5000元。"},
        )
    finally:
        app.dependency_overrides.pop(get_brief_service, None)


async def test_malformed_json_is_repaired_once(api_client: httpx.AsyncClient) -> None:
    provider = ScriptedProvider(
        [
            '{"destination":"重庆","start_date":',
            fixture_content("valid_trip_brief.json"),
        ]
    )

    response = await parse_with_provider(api_client, provider)

    assert response.status_code == 200, response.text
    assert response.json()["brief"]["destination"] == "重庆"
    assert provider.call_count == 2
    assert "上一次输出未通过校验" in provider.requests[1].user_prompt
    run = await app.state.test_session.scalar(
        select(AgentRun)
        .where(AgentRun.purpose == "brief_parse")
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    assert run is not None
    assert run.estimated_cost_minor == get_settings().brief_parse_max_cost_minor


async def test_invalid_date_range_is_repaired(api_client: httpx.AsyncClient) -> None:
    provider = ScriptedProvider(
        [
            fixture_content("invalid_date_range.json"),
            fixture_content("valid_trip_brief.json"),
        ]
    )

    response = await parse_with_provider(api_client, provider)

    assert response.status_code == 200, response.text
    assert response.json()["brief"]["end_date"] == "2026-12-03"
    assert provider.call_count == 2
    assert "start_date must be on or before end_date" in provider.requests[1].user_prompt


async def test_invalid_date_range_is_repaired_before_missing_fields(
    api_client: httpx.AsyncClient,
) -> None:
    provider = ScriptedProvider(
        [
            fixture_content("invalid_date_range.json").replace(
                '"budget_minor": 500000',
                '"budget_minor": null',
            ),
            fixture_content("valid_trip_brief.json"),
        ]
    )

    response = await parse_with_provider(api_client, provider)

    assert response.status_code == 200, response.text
    assert provider.call_count == 2
    assert "start_date must be on or before end_date" in provider.requests[1].user_prompt


async def test_invalid_json_stops_after_two_repairs(
    api_client: httpx.AsyncClient,
) -> None:
    provider = ScriptedProvider(['{"destination":'])

    response = await parse_with_provider(api_client, provider)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_llm_output"
    assert provider.call_count == 3

    run = await app.state.test_session.scalar(
        select(AgentRun).where(AgentRun.purpose == "brief_parse")
    )
    assert run is not None
    assert run.status == "failed"
    assert run.error_code == "invalid_llm_output"
    assert run.input_tokens == 30
    assert run.output_tokens == 60
    assert run.latency_ms == 15


async def test_timeout_returns_gateway_timeout(api_client: httpx.AsyncClient) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])

    async def service_override() -> BriefService:
        return BriefService(
            app.state.test_session,
            TimeoutProvider(),
            get_settings(),
        )

    app.dependency_overrides[get_brief_service] = service_override
    try:
        response = await api_client.post(
            "/api/v1/briefs/parse",
            headers=auth_headers(token),
            json={"text": "2026年12月1日到12月3日，2个人去重庆，预算5000元。"},
        )
    finally:
        app.dependency_overrides.pop(get_brief_service, None)

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "llm_timeout"
    run = await app.state.test_session.scalar(
        select(AgentRun).where(AgentRun.purpose == "brief_parse")
    )
    assert run is not None
    assert run.status == "failed"
    assert run.error_code == "llm_timeout"
    assert run.estimated_cost_minor == get_settings().brief_parse_max_cost_minor
