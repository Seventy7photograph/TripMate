# 文件说明：Skill 运行时：Router 安全回退。
from typing import Literal

from app.skills.router import (
    SkillRouteBudget,
    SkillRouteDecision,
)


def fallback_route_decision(reason: str) -> SkillRouteDecision:
    normalized = reason.strip()[:300] or "router unavailable"
    intent: Literal["create_trip_plan"] = "create_trip_plan"
    return SkillRouteDecision(
        intent=intent,
        confidence=0.5,
        selected_skills=[],
        needed_clarifications=[],
        budget=SkillRouteBudget(
            max_tool_calls=0,
            max_tokens=0,
            allowed_tools=[],
            allowed_mcp_connectors=[],
        ),
        requires_confirmation=False,
        fallback_reason=normalized,
        repair_attempts=1,
    )
