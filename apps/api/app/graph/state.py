# 文件说明：LangGraph 编排：state。
from typing import Literal, TypedDict

GraphStatus = Literal["running", "retrying", "repairing", "completed", "partial", "failed"]


class TravelGraphState(TypedDict, total=False):
    trip_id: str
    version: int
    brief: dict[str, object]
    brief_confirmed: bool
    candidates: list[dict[str, object]]
    evidence_ids_by_place: dict[str, str]
    evidence_records: list[dict[str, object]]
    evidence_issues: list[dict[str, object]]
    draft: dict[str, object] | None
    issues: list[dict[str, object]]
    loop_count: int
    composer_attempts: int
    tool_call_count: int
    deadline_at: str
    status: GraphStatus
    error_code: str | None
    error_message: str | None
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost_minor: int
    model_name: str
    provider_name: str
    skills_used: list[dict[str, object]]
    skill_route: dict[str, object] | None
    prompt_versions: list[dict[str, str]]
    events: list[dict[str, object]]
