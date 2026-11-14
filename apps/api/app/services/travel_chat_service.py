# 文件说明：业务服务：travel_chat_service。
"""将旅行对话结果、Skill 和 Tool 审计信息持久化为 AgentRun。"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.travel_chat import TravelChatAgent, TravelChatResult
from app.models.agent_run import AgentRun
from app.providers.llm.base import (
    LlmProviderError,
    LlmRateLimitError,
    LlmTimeoutError,
)
from app.schemas.chat import ChatHistoryTurn, TravelChatResponse


class TravelChatService:
    def __init__(self, session: AsyncSession, agent: TravelChatAgent) -> None:
        self._session = session
        self._agent = agent

    async def respond(
        self,
        *,
        owner_id: UUID,
        message: str,
        history: list[ChatHistoryTurn],
        documents: list[tuple[str, str]] | None = None,
        image_data_urls: tuple[str, ...] = (),
    ) -> TravelChatResponse:
        run = AgentRun(
            trip_id=None,
            created_by=owner_id,
            status="running",
            progress=25,
            purpose="travel_chat",
            provider=self._agent.provider_name,
            model_name=self._agent.model_name,
            events=[
                {
                    "sequence": 1,
                    "type": "stage",
                    "stage": "intent_routing",
                    "message": "正在识别旅行意图",
                }
            ],
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()
        await self._session.refresh(run)
        try:
            result = await self._agent.respond(
                owner_id=owner_id,
                message=message,
                history=history,
                documents=documents,
                image_data_urls=image_data_urls,
            )
        except Exception as exc:
            await self._record_failure(run, exc)
            raise
        self._apply_result(run, result)
        await self._session.flush()
        await self._session.refresh(run)
        await self._session.commit()
        return result.response

    def _apply_result(self, run: AgentRun, result: TravelChatResult) -> None:
        response = result.response
        run.status = "completed"
        run.progress = 100
        run.model_name = response.model_name or run.model_name
        run.input_tokens = result.usage.input_tokens
        run.output_tokens = result.usage.output_tokens
        run.latency_ms = result.usage.latency_ms
        run.estimated_cost_minor = result.usage.estimated_cost_minor
        run.tool_call_count = (
            len(response.used_tools)
            + result.usage.search_count
            + result.usage.fetch_count
        )
        run.skills_used = result.skills_used
        run.prompt_versions = result.prompt_versions
        run.skill_route = result.skill_route
        run.result = response.model_dump(mode="json")
        run.events = [
            *run.events,
            {
                "sequence": 2,
                "type": "stage",
                "stage": "intent_routed",
                "status": "completed",
                "message": f"识别为 {response.intent}",
                "payload": {
                    "confidence": response.confidence,
                    "selected_skills": response.selected_skills,
                    "source_count": len(response.sources),
                },
            },
            {
                "sequence": 3,
                "type": "complete",
                "status": "completed",
                "message": "旅行对话响应完成",
            },
        ]
        run.finished_at = datetime.now(UTC)

    async def _record_failure(self, run: AgentRun, exc: Exception) -> None:
        run.status = "failed"
        run.progress = 100
        run.error_code = _error_code(exc)
        run.error_message = "Travel chat request failed"
        run.finished_at = datetime.now(UTC)
        run.events = [
            *run.events,
            {
                "sequence": 2,
                "type": "error",
                "status": "failed",
                "message": "旅行对话处理失败",
            },
        ]
        await self._session.commit()


def _error_code(exc: Exception) -> str:
    if isinstance(exc, LlmTimeoutError):
        return "llm_timeout"
    if isinstance(exc, LlmRateLimitError):
        return "llm_rate_limited"
    if isinstance(exc, LlmProviderError):
        return "llm_provider_error"
    return "travel_chat_failed"
