# 文件说明：业务服务：travel_chat_service。
"""将旅行对话结果、Skill 和 Tool 审计信息持久化为 AgentRun。"""

import json
from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.travel_chat import TravelChatAgent, TravelChatResult
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation as ConversationModel
from app.models.tool_call_log import ToolCallLog
from app.providers.llm.base import (
    LlmProviderError,
    LlmRateLimitError,
    LlmTimeoutError,
)
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chat import ChatHistoryTurn, TravelChatResponse
from app.schemas.planning_draft import PlanningDraft
from app.services.conversation_service import ConversationNotFoundError
from app.services.provider_health_service import ProviderHealthService


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
        attachment_ids: list[UUID] | None = None,
        conversation_id: UUID | None = None,
        client_today: date | None = None,
    ) -> TravelChatResponse:
        planning_draft: PlanningDraft | None = None
        effective_history = history
        if conversation_id is not None:
            conversation = await ConversationRepository(
                self._session
            ).get_for_owner(
                owner_id=owner_id,
                conversation_id=conversation_id,
            )
            if conversation is None:
                raise ConversationNotFoundError
            effective_history = (
                _stored_conversation_history(
                    conversation,
                    current_message=message,
                )
                or history
            )
            if conversation.planning_draft:
                planning_draft = PlanningDraft.model_validate(
                    conversation.planning_draft
                )
        effective_today = effective_client_today(client_today)
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
                history=effective_history,
                documents=documents,
                image_data_urls=image_data_urls,
                attachment_ids=attachment_ids,
                planning_draft=planning_draft,
                today=effective_today,
            )
        except Exception as exc:
            await self._record_failure(run, exc)
            raise
        await self._apply_result(run, result)
        await self._session.flush()
        await self._session.refresh(run)
        await self._session.commit()
        return result.response

    async def _apply_result(
        self,
        run: AgentRun,
        result: TravelChatResult,
    ) -> None:
        response = result.response
        run.status = "completed"
        run.progress = 100
        run.model_name = response.model_name or run.model_name
        run.input_tokens = result.usage.input_tokens
        run.output_tokens = result.usage.output_tokens
        run.latency_ms = result.usage.latency_ms
        run.estimated_cost_minor = result.usage.estimated_cost_minor
        run.tool_call_count = (
            len(result.tool_audits)
            + result.usage.search_count
            + result.usage.fetch_count
        )
        run.skills_used = result.skills_used
        run.prompt_versions = result.prompt_versions
        run.skill_route = result.skill_route
        run.result = response.model_dump(mode="json")
        provider_health = ProviderHealthService(self._session)
        for audit in result.tool_audits:
            self._session.add(
                ToolCallLog(
                    agent_run_id=run.id,
                    tool_name=audit.tool_name,
                    provider=audit.provider,
                    input_hash=audit.input_hash,
                    status=audit.status,
                    latency_ms=audit.latency_ms,
                    estimated_cost_minor=audit.estimated_cost_minor,
                    error_code=audit.error_code,
                )
            )
            await provider_health.record_audit(audit)
        await provider_health.record_llm(
            provider_name=run.provider,
            status="healthy" if run.status == "completed" else "degraded",
            latency_ms=run.latency_ms,
            model_name=run.model_name,
        )
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
                    "skill_failures": response.skill_failures,
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
        await ProviderHealthService(self._session).record_llm(
            provider_name=run.provider,
            status="degraded",
            latency_ms=int(
                (
                    datetime.now(UTC) - (run.started_at or datetime.now(UTC))
                ).total_seconds()
                * 1_000
            ),
            model_name=run.model_name,
            error_code=_error_code(exc),
        )
        await self._session.commit()


def _error_code(exc: Exception) -> str:
    if isinstance(exc, LlmTimeoutError):
        return "llm_timeout"
    if isinstance(exc, LlmRateLimitError):
        return "llm_rate_limited"
    if isinstance(exc, LlmProviderError):
        return "llm_provider_error"
    return "travel_chat_failed"


def effective_client_today(client_today: date | None) -> date:
    server_today = _shanghai_today()
    if (
        client_today is not None
        and abs(client_today - server_today) <= timedelta(days=1)
    ):
        return client_today
    return server_today


def _shanghai_today() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def _stored_conversation_history(
    conversation: ConversationModel,
    *,
    current_message: str,
) -> list[ChatHistoryTurn]:
    messages = list(conversation.messages)[-21:]
    history: list[ChatHistoryTurn] = []
    normalized_current = current_message.strip()
    for index, message in enumerate(messages):
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue
        text = message.get("text")
        if (
            index == len(messages) - 1
            and role == "user"
            and isinstance(text, str)
            and text.strip() == normalized_current
        ):
            continue
        parts: list[str] = []
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
        questions = message.get("questions")
        if isinstance(questions, list):
            normalized_questions = [
                str(question).strip()
                for question in questions
                if str(question).strip()
            ]
            if normalized_questions:
                parts.append(f"待确认：{'；'.join(normalized_questions)}")
        draft = message.get("draft")
        if isinstance(draft, dict) and draft:
            parts.append(
                "当前规划草稿："
                f"{json.dumps(draft, ensure_ascii=False, separators=(',', ':'))}"
            )
        content = "\n".join(parts).strip()
        if content:
            history.append(
                ChatHistoryTurn(
                    role=role,
                    content=content[:8_000],
                )
            )
    return history[-20:]
