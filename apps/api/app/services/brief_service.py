# 文件说明：业务服务：brief_service。
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.requirement_parser import (
    RequirementParseError,
    RequirementParser,
    RequirementParseResult,
)
from app.models.agent_run import AgentRun
from app.providers.llm.base import StructuredLlmProvider
from app.services.provider_health_service import ProviderHealthService


class BriefService:
    def __init__(
        self,
        session: AsyncSession,
        provider: StructuredLlmProvider,
        *,
        max_repairs: int = 2,
    ) -> None:
        self._session = session
        self._provider = provider
        self._parser = RequirementParser(provider, max_repairs=max_repairs)

    async def parse(
        self,
        *,
        owner_id: UUID,
        text: str,
        documents: list[tuple[str, str]] | None = None,
        image_data_urls: tuple[str, ...] = (),
    ) -> RequirementParseResult:
        run = AgentRun(
            trip_id=None,
            created_by=owner_id,
            status="running",
            progress=25,
            purpose="brief_parse",
            provider=self._provider.provider_name,
            model_name=self._provider.model_name,
            events=[
                {
                    "sequence": 1,
                    "type": "stage",
                    "stage": "requirement_parse",
                    "message": "正在解析旅行需求",
                }
            ],
            started_at=datetime.now(UTC),
        )
        self._session.add(run)
        await self._session.flush()
        await self._session.refresh(run)

        try:
            result = await self._parser.parse(
                text,
                documents=documents,
                image_data_urls=image_data_urls,
            )
        except RequirementParseError as exc:
            await self._record_failure(
                run,
                error_code="invalid_llm_output",
                input_tokens=exc.input_tokens,
                output_tokens=exc.output_tokens,
                latency_ms=exc.latency_ms,
                model_name=exc.model_name or run.model_name,
                provider=exc.provider_name or run.provider,
                estimated_cost_minor=exc.estimated_cost_minor,
                prompt_versions=exc.prompt_versions,
            )
            raise
        except Exception as exc:
            await self._record_failure(
                run,
                error_code=self._error_code(exc),
                model_name=run.model_name,
                provider=run.provider,
            )
            raise

        run.status = "completed"
        run.progress = 100
        run.model_name = result.model_name
        run.provider = result.provider_name
        run.input_tokens = result.input_tokens
        run.output_tokens = result.output_tokens
        run.latency_ms = result.latency_ms
        run.estimated_cost_minor = result.estimated_cost_minor
        run.prompt_versions = result.prompt_versions
        run.result = result.response.model_dump(mode="json")
        run.events = [
            *run.events,
            {
                "sequence": 2,
                "type": "validation",
                "status": "passed",
                "message": "旅行需求结构校验通过",
                "payload": {"attempts": result.attempts},
            },
            {
                "sequence": 3,
                "type": "complete",
                "status": "completed",
                "message": "旅行需求解析完成",
            },
        ]
        run.finished_at = datetime.now(UTC)
        await ProviderHealthService(self._session).record_llm(
            provider_name=run.provider,
            status="healthy",
            latency_ms=run.latency_ms,
            model_name=run.model_name,
        )
        await self._session.commit()
        return result

    async def _record_failure(
        self,
        run: AgentRun,
        *,
        error_code: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = 0,
        model_name: str,
        provider: str,
        estimated_cost_minor: int = 0,
        prompt_versions: list[dict[str, str]] | None = None,
    ) -> None:
        run.status = "failed"
        run.progress = 100
        run.model_name = model_name
        run.provider = provider
        run.input_tokens = input_tokens
        run.output_tokens = output_tokens
        run.latency_ms = latency_ms
        run.estimated_cost_minor = estimated_cost_minor
        run.prompt_versions = prompt_versions or []
        run.error_code = error_code
        run.error_message = "Requirement parsing failed"
        run.events = [
            *run.events,
            {
                "sequence": 2,
                "type": "error",
                "status": "failed",
                "message": "旅行需求解析失败",
            },
        ]
        run.finished_at = datetime.now(UTC)
        await ProviderHealthService(self._session).record_llm(
            provider_name=provider,
            status="degraded",
            latency_ms=latency_ms,
            model_name=model_name,
            error_code=error_code,
        )
        await self._session.commit()

    @staticmethod
    def _error_code(exc: Exception) -> str:
        from app.providers.llm.base import LlmRateLimitError, LlmTimeoutError

        if isinstance(exc, LlmTimeoutError):
            return "llm_timeout"
        if isinstance(exc, LlmRateLimitError):
            return "llm_rate_limited"
        return "llm_provider_error"
