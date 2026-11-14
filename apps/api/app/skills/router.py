# 文件说明：Skill 运行时：受控 Router。
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ai import TripBriefContract
from app.skills.manifest import SkillManifest

SkillIntent = Literal[
    "create_trip_plan",
    "clarify",
    "unsupported",
]


class SkillRouteBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_tool_calls: int = Field(ge=0, le=32)
    max_tokens: int = Field(ge=0, le=128_000)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_mcp_connectors: list[str] = Field(default_factory=list)


class SkillRouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: SkillIntent
    confidence: float = Field(ge=0, le=1)
    selected_skills: list[str] = Field(default_factory=list)
    needed_clarifications: list[str] = Field(default_factory=list)
    budget: SkillRouteBudget
    requires_confirmation: bool
    fallback_reason: str | None = None
    repair_attempts: int = Field(default=0, ge=0, le=1)

    @property
    def needs_clarification(self) -> bool:
        return bool(self.needed_clarifications) and self.fallback_reason is None


class SkillRouter:
    def route(
        self,
        *,
        text: str | None = None,
        brief: TripBriefContract | None = None,
        available_skills: list[SkillManifest],
        requested_skills: list[str] | None = None,
    ) -> SkillRouteDecision:
        active = {
            manifest.name: manifest
            for manifest in available_skills
            if manifest.status == "active"
        }
        normalized = (text or "").strip()
        if brief is None:
            return self._route_text(normalized, active)

        selected = self._select_from_brief(brief, normalized, active)
        if requested_skills:
            selected = [
                name for name in requested_skills if name in selected
            ]
        missing = self._missing_brief_fields(brief)
        confidence = 0.92 if not missing else 0.64
        return self._decision(
            intent="create_trip_plan" if not missing else "clarify",
            confidence=confidence,
            selected=selected,
            clarifications=missing,
            available=active,
            requires_confirmation=True,
        )

    def _route_text(
        self,
        text: str,
        available: dict[str, SkillManifest],
    ) -> SkillRouteDecision:
        if not text or any(
            term in text
            for term in ("随便", "安静的地方", "不知道", "看着办")
        ):
            return self._decision(
                intent="clarify",
                confidence=0.35,
                selected=[],
                clarifications=[
                    "请补充具体目的地。",
                    "请补充出发和返程日期。",
                ],
                available=available,
                requires_confirmation=False,
            )
        if any(
            term in text.casefold()
            for term in ("python", "写代码", "股票", "彩票")
        ):
            return self._decision(
                intent="unsupported",
                confidence=0.98,
                selected=[],
                clarifications=[],
                available=available,
                requires_confirmation=False,
            )
        return self._decision(
            intent="clarify",
            confidence=0.62,
            selected=[],
            clarifications=["请补充完整日期、人数和预算，确认后再规划。"],
            available=available,
            requires_confirmation=False,
        )

    @staticmethod
    def _select_from_brief(
        brief: TripBriefContract,
        text: str,
        available: dict[str, SkillManifest],
    ) -> list[str]:
        searchable = " ".join(
            [
                text,
                brief.destination,
                *brief.interests,
                *brief.lodging_preferences,
                *brief.must_visit,
                *brief.constraints,
            ]
        )
        selected = ["route-optimization"]
        if brief.must_visit or any(
            term in searchable
            for term in ("景点", "古建", "古城", "博物馆", "目的地")
        ):
            selected.append("destination-research")
        if any(
            term in searchable
            for term in ("美食", "小吃", "餐厅", "早餐", "午餐", "晚餐")
        ):
            selected.append("food-planning")
        if brief.lodging_preferences or "住宿" in searchable:
            selected.append("lodging-area-selection")
        if any(
            term in searchable
            for term in ("天气", "穿衣", "户外", "自然", "高海拔")
        ):
            selected.append("weather-and-clothing")
        if any(
            term in searchable
            for term in ("安全", "老人", "儿童", "孕期", "慢性病")
        ):
            selected.append("safety-briefing")
        return [
            name
            for name in dict.fromkeys(selected)
            if name in available
        ]

    @staticmethod
    def _missing_brief_fields(brief: TripBriefContract) -> list[str]:
        missing: list[str] = []
        if not brief.destination.strip():
            missing.append("目的地")
        if brief.start_date > brief.end_date:
            missing.append("有效日期范围")
        if brief.party_size < 1:
            missing.append("出行人数")
        return missing

    @staticmethod
    def _decision(
        *,
        intent: SkillIntent,
        confidence: float,
        selected: list[str],
        clarifications: list[str],
        available: dict[str, SkillManifest],
        requires_confirmation: bool,
    ) -> SkillRouteDecision:
        manifests = [available[name] for name in selected]
        return SkillRouteDecision(
            intent=intent,
            confidence=confidence,
            selected_skills=selected,
            needed_clarifications=clarifications,
            budget=SkillRouteBudget(
                max_tool_calls=min(
                    sum(manifest.max_tool_calls for manifest in manifests),
                    12,
                ),
                max_tokens=min(
                    sum(manifest.max_tokens for manifest in manifests),
                    32_000,
                ),
                allowed_tools=list(
                    dict.fromkeys(
                        tool
                        for manifest in manifests
                        for tool in manifest.allowed_tools
                    )
                ),
                allowed_mcp_connectors=list(
                    dict.fromkeys(
                        connector
                        for manifest in manifests
                        for connector in manifest.allowed_mcp_connectors
                    )
                ),
            ),
            requires_confirmation=requires_confirmation,
        )
