# 文件说明：业务服务：model_config_service。
import base64
import hashlib
from dataclasses import dataclass
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.admin_audit_log import AdminAuditLog
from app.models.model_config import AgentModelConfig
from app.schemas.admin import (
    ModelConfigResponse,
    ModelConfigUpdateRequest,
    ModelStage,
)
from app.services.url_safety import UnsafeUrlError, validate_external_http_url

MODEL_STAGE_LABELS: dict[ModelStage, str] = {
    "brief_parse": "旅行需求解析",
    "research_planner": "地点研究规划",
    "itinerary_composer": "行程编排",
    "travel_chat": "旅行对话与意图识别",
}


class ModelConfigError(Exception):
    pass


class ModelStageNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ResolvedModelConfig:
    stage: ModelStage
    provider_profile: str
    base_url: str
    model_name: str
    api_key: SecretStr | None
    timeout_seconds: int
    max_retries: int


class ModelConfigService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def list_configs(self) -> list[ModelConfigResponse]:
        rows = {
            row.stage: row
            for row in (await self._session.execute(select(AgentModelConfig))).scalars()
        }
        return [
            self._response(stage, rows.get(stage))
            for stage in MODEL_STAGE_LABELS
        ]

    async def update(
        self,
        *,
        stage: str,
        payload: ModelConfigUpdateRequest,
        actor_id: UUID,
    ) -> ModelConfigResponse:
        stage_key = self._stage(stage)
        try:
            base_url = validate_external_http_url(
                payload.base_url,
                allowed_hosts=(
                    self._settings.provider_allowed_host_list or None
                ),
                allow_private=self._settings.allow_private_provider_urls,
            )
        except UnsafeUrlError as exc:
            raise ModelConfigError(str(exc)) from exc
        model = await self._session.get(AgentModelConfig, stage_key)
        previous_api_key = None if model is None else model.api_key_ciphertext
        if model is None:
            model = AgentModelConfig(
                stage=stage_key,
                provider_profile=payload.provider_profile,
                base_url=base_url,
                model_name=payload.model_name,
                timeout_seconds=payload.timeout_seconds,
                max_retries=payload.max_retries,
                updated_by=actor_id,
            )
            self._session.add(model)
        else:
            model.provider_profile = payload.provider_profile
            model.base_url = base_url
            model.model_name = payload.model_name
            model.timeout_seconds = payload.timeout_seconds
            model.max_retries = payload.max_retries
            model.updated_by = actor_id

        api_key_changed = False
        if payload.clear_api_key:
            model.api_key_ciphertext = None
            api_key_changed = previous_api_key is not None
        elif payload.api_key is not None:
            raw_key = payload.api_key.get_secret_value().strip()
            if raw_key:
                model.api_key_ciphertext = self._encrypt(raw_key)
                api_key_changed = True

        self._session.add(
            AdminAuditLog(
                actor_id=actor_id,
                action="model_config.update",
                target_type="agent_model_config",
                target_id=stage_key,
                details={
                    "provider_profile": payload.provider_profile,
                    "base_url": base_url,
                    "model_name": payload.model_name,
                    "timeout_seconds": payload.timeout_seconds,
                    "max_retries": payload.max_retries,
                    "api_key_changed": api_key_changed,
                },
            )
        )
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return self._response(stage_key, model)

    async def resolve(self, stage: ModelStage) -> ResolvedModelConfig:
        if not self._settings.model_config_db_enabled:
            return ResolvedModelConfig(
                stage=stage,
                provider_profile=self._settings.provider_profile,
                base_url=self._settings.llm_base_url,
                model_name=self._settings.llm_model,
                api_key=self._settings.llm_api_key,
                timeout_seconds=int(self._settings.llm_timeout_seconds),
                max_retries=self._settings.llm_max_retries,
            )

        model = await self._session.get(AgentModelConfig, stage)
        if self._settings.app_env == "production" and model is not None:
            if model.provider_profile != "live":
                raise ModelConfigError(
                    f"{stage} must use the live profile in production"
                )
        if model is None:
            return ResolvedModelConfig(
                stage=stage,
                provider_profile=self._settings.provider_profile,
                base_url=self._settings.llm_base_url,
                model_name=self._settings.llm_model,
                api_key=self._settings.llm_api_key,
                timeout_seconds=int(self._settings.llm_timeout_seconds),
                max_retries=self._settings.llm_max_retries,
            )

        try:
            base_url = validate_external_http_url(
                model.base_url,
                allowed_hosts=(
                    self._settings.provider_allowed_host_list or None
                ),
                allow_private=self._settings.allow_private_provider_urls,
            )
        except UnsafeUrlError as exc:
            raise ModelConfigError(str(exc)) from exc

        api_key = self._settings.llm_api_key
        if model.api_key_ciphertext:
            api_key = SecretStr(self._decrypt(model.api_key_ciphertext))
        if (
            model.provider_profile == "live"
            and (api_key is None or not api_key.get_secret_value().strip())
        ):
            raise ModelConfigError(f"{stage} requires an API key for live profile")
        if model.provider_profile == "live" and not model.model_name.strip():
            raise ModelConfigError(f"{stage} requires a model name")
        return ResolvedModelConfig(
            stage=stage,
            provider_profile=model.provider_profile,
            base_url=base_url,
            model_name=model.model_name,
            api_key=api_key,
            timeout_seconds=model.timeout_seconds,
            max_retries=model.max_retries,
        )

    async def settings_for(self, stage: ModelStage) -> Settings:
        resolved = await self.resolve(stage)
        return self._settings.model_copy(
            update={
                "provider_profile": resolved.provider_profile,
                "llm_base_url": resolved.base_url,
                "llm_model": resolved.model_name,
                "llm_api_key": resolved.api_key,
                "llm_timeout_seconds": resolved.timeout_seconds,
                "llm_max_retries": resolved.max_retries,
            }
        )

    def _response(
        self,
        stage: ModelStage,
        model: AgentModelConfig | None,
    ) -> ModelConfigResponse:
        if model is None:
            return ModelConfigResponse(
                stage=stage,
                label=MODEL_STAGE_LABELS[stage],
                provider_profile=self._settings.provider_profile,
                base_url=self._settings.llm_base_url,
                model_name=self._settings.llm_model,
                api_key_configured=(
                    self._settings.llm_api_key is not None
                    and bool(
                        self._settings.llm_api_key.get_secret_value().strip()
                    )
                ),
                timeout_seconds=int(self._settings.llm_timeout_seconds),
                max_retries=self._settings.llm_max_retries,
                source="environment",
                updated_at=None,
            )
        return ModelConfigResponse(
            stage=stage,
            label=MODEL_STAGE_LABELS[stage],
            provider_profile=model.provider_profile,  # type: ignore[arg-type]
            base_url=model.base_url,
            model_name=model.model_name,
            api_key_configured=(
                model.api_key_ciphertext is not None
                or (
                    self._settings.llm_api_key is not None
                    and bool(
                        self._settings.llm_api_key.get_secret_value().strip()
                    )
                )
            ),
            timeout_seconds=model.timeout_seconds,
            max_retries=model.max_retries,
            source="database",
            updated_at=model.updated_at,
        )

    def _encrypt(self, value: str) -> str:
        return self._fernet().encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        try:
            return self._fernet().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ModelConfigError(
                "Stored model API key cannot be decrypted with the current key"
            ) from exc

    def _fernet(self) -> Fernet:
        secret = (
            self._settings.model_config_encryption_key
            or self._settings.jwt_secret
        ).get_secret_value()
        digest = hashlib.sha256(secret.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    @staticmethod
    def _stage(stage: str) -> ModelStage:
        if stage not in MODEL_STAGE_LABELS:
            raise ModelStageNotFoundError
        return stage  # type: ignore[return-value]
