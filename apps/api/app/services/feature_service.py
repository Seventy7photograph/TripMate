# 文件说明：业务服务：feature_service。
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit_log import AdminAuditLog
from app.models.feature_flag import FeatureFlag

FEATURE_DEFINITIONS: dict[str, tuple[str, str]] = {
    "ai_planning": ("AI 行程规划", "允许创建新的 LangGraph 规划任务"),
    "brief_parsing": ("旅行需求解析", "允许调用 LLM 解析自然语言旅行需求"),
    "llm_provider": ("LLM Provider", "允许调用已配置的语言模型 Provider"),
    "map_provider": ("地图 Provider", "允许地点搜索、地理编码和路线计算"),
    "travel_chat": ("旅行对话", "允许使用意图识别、旅行问答和网页研究"),
    "agent_skills_enabled": (
        "Agent Skills",
        "允许新任务使用受控 Skill 运行时；关闭后回退单主 Agent",
    ),
    "agent_skill_router_enabled": (
        "Skill Router",
        "允许新任务使用 Skill 路由；关闭后回退现有规划链",
    ),
    "mcp_gateway_enabled": (
        "MCP Gateway",
        "允许只读 MCP connector；关闭后回退本地 Provider Tool",
    ),
    "weather_provider": (
        "Weather Provider",
        "允许天气与海拔数据查询；关闭后相关 Skill 标记未知",
    ),
}


class FeatureDisabledError(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(f"Feature {key} is disabled")
        self.key = key


class FeatureNotFoundError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class FeatureFlagView:
    key: str
    label: str
    description: str
    enabled: bool
    updated_by: UUID | None
    updated_at: datetime | None


class FeatureFlagService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_flags(self) -> list[FeatureFlagView]:
        result = await self._session.execute(select(FeatureFlag))
        rows = {row.key: row for row in result.scalars()}
        return [
            self._to_view(
                key,
                row=rows.get(key),
            )
            for key in FEATURE_DEFINITIONS
        ]

    async def is_enabled(self, key: str) -> bool:
        self._require_known(key)
        model = await self._session.get(FeatureFlag, key)
        return True if model is None else model.enabled

    async def require_enabled(self, key: str) -> None:
        if not await self.is_enabled(key):
            raise FeatureDisabledError(key)

    async def require_all(self, keys: list[str]) -> None:
        for key in keys:
            await self.require_enabled(key)

    async def toggle(
        self,
        *,
        key: str,
        enabled: bool,
        actor_id: UUID,
        reason: str | None,
    ) -> FeatureFlagView:
        self._require_known(key)
        label, description = FEATURE_DEFINITIONS[key]
        model = await self._session.get(FeatureFlag, key)
        previous = True if model is None else model.enabled
        if model is None:
            model = FeatureFlag(
                key=key,
                enabled=enabled,
                description=f"{label}：{description}",
                updated_by=actor_id,
            )
            self._session.add(model)
        else:
            model.enabled = enabled
            model.updated_by = actor_id
        self._session.add(
            AdminAuditLog(
                actor_id=actor_id,
                action="feature.toggle",
                target_type="feature_flag",
                target_id=key,
                details={
                    "previous_enabled": previous,
                    "enabled": enabled,
                    "reason": reason,
                },
            )
        )
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return self._to_view(key, row=model)

    @staticmethod
    def _require_known(key: str) -> None:
        if key not in FEATURE_DEFINITIONS:
            raise FeatureNotFoundError

    @staticmethod
    def _to_view(key: str, *, row: FeatureFlag | None) -> FeatureFlagView:
        label, description = FEATURE_DEFINITIONS[key]
        return FeatureFlagView(
            key=key,
            label=label,
            description=description,
            enabled=True if row is None else row.enabled,
            updated_by=None if row is None else row.updated_by,
            updated_at=None if row is None else row.updated_at,
        )
