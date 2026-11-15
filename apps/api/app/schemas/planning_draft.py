# 文件说明：Pydantic 数据契约：planning_draft。
from pydantic import Field, field_validator

from app.domain.transport import TransportStrategy
from app.schemas.requirement import TripBriefExtraction


class PlanningDraft(TripBriefExtraction):
    date_context: dict[str, object] = Field(default_factory=dict)
    transport_strategy: TransportStrategy = Field(
        default_factory=TransportStrategy
    )
    pending_questions: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("pending_questions")
    @classmethod
    def normalize_pending_questions(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    def to_record(self) -> dict[str, object]:
        return self.model_dump(
            mode="json",
            exclude_none=True,
            exclude_defaults=True,
        )
