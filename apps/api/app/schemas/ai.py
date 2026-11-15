# 文件说明：Pydantic 数据契约：ai。
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.transport import TransportStrategy
from app.domain.trip import TripPace

PlanningEventType = Literal["stage", "tool_call", "validation", "complete", "error"]
PlanningStatus = Literal["queued", "running", "completed", "partial", "failed"]


class TripBriefContract(BaseModel):
    destination: str
    origin: str | None = None
    start_date: date
    end_date: date
    party_size: int = Field(ge=1, le=20)
    budget_minor: int | None = Field(default=None, ge=0)
    currency: str = "CNY"
    interests: list[str] = Field(default_factory=list)
    pace: TripPace = "balanced"
    transport_preferences: list[str] = Field(default_factory=list)
    transport_strategy: TransportStrategy = Field(
        default_factory=TransportStrategy
    )
    lodging_preferences: list[str] = Field(default_factory=list)
    must_visit: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self) -> "TripBriefContract":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class SourceMetadataContract(BaseModel):
    provider: str
    provider_place_id: str | None = None
    source_url: str | None = None
    queried_at: datetime
    freshness: Literal["live", "cached", "mock", "unknown"]
    confidence: float = Field(ge=0, le=1)


class ItineraryStopContract(BaseModel):
    id: str
    place_id: str
    place_name: str | None = None
    start_at: datetime
    duration_minutes: int = Field(gt=0)
    estimated_cost_minor: int = Field(ge=0)
    source: SourceMetadataContract


class TripDayContract(BaseModel):
    id: str
    date: date
    theme: str | None = None
    stops: list[ItineraryStopContract]


class WeatherPlanContract(BaseModel):
    status: Literal["known", "unknown"] = "unknown"
    summary: str | None = None
    temperature_max_c: int | None = None
    temperature_min_c: int | None = None
    precipitation_probability: int | None = None
    clothing_advice: list[str] = Field(default_factory=list)
    risk: Literal["low", "moderate", "high"] = "low"
    evidence_ids: list[str] = Field(default_factory=list)


class MealPlanContract(BaseModel):
    meal: Literal["breakfast", "lunch", "dinner"]
    status: Literal["known", "unknown"] = "unknown"
    place_name: str | None = None
    timing: str | None = None
    opening_hours_status: Literal["known", "unknown"] = "unknown"
    evidence_ids: list[str] = Field(default_factory=list)


class TransportPlanContract(BaseModel):
    mode: str
    duration_minutes: int | None = Field(default=None, ge=0)
    distance_m: int | None = Field(default=None, ge=0)
    summary: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class LodgingAreaPlanContract(BaseModel):
    status: Literal["known", "unknown"] = "unknown"
    area: str | None = None
    reason: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class SafetyPlanContract(BaseModel):
    level: Literal["low", "moderate", "warning", "high"] = "low"
    reminders: list[str] = Field(default_factory=list)
    disclaimer: str = "安全提示不替代医疗意见。"
    evidence_ids: list[str] = Field(default_factory=list)


class DayPlanContract(TripDayContract):
    weather: WeatherPlanContract = Field(default_factory=WeatherPlanContract)
    meals: list[MealPlanContract] = Field(default_factory=list)
    transport: list[TransportPlanContract] = Field(default_factory=list)
    lodging_area: LodgingAreaPlanContract = Field(
        default_factory=LodgingAreaPlanContract
    )
    safety: SafetyPlanContract = Field(default_factory=SafetyPlanContract)
    daily_summary: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ValidationIssueContract(BaseModel):
    code: Literal[
        "unknown_place",
        "missing_coordinates",
        "route_unavailable",
        "time_conflict",
        "opening_hours_conflict",
        "commute_too_long",
        "budget_exceeded",
        "stale_data",
        "invalid_schema",
        "evidence_missing",
        "evidence_stale",
        "evidence_conflict",
        "unsupported_claim",
    ]
    severity: Literal["info", "warning", "error", "fatal"]
    path: str
    message: str
    repair_hint: str | None = None


class ItineraryDraftContract(BaseModel):
    trip_id: str
    version: int
    days: list[DayPlanContract]
    validation_summary: list[ValidationIssueContract] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def coerce_legacy_days(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        raw_days = value.get("days")
        if not isinstance(raw_days, list):
            return value
        converted: list[object] = []
        for day in raw_days:
            if isinstance(day, DayPlanContract):
                converted.append(day)
            elif isinstance(day, TripDayContract):
                converted.append(
                    DayPlanContract(**day.model_dump())
                )
            else:
                converted.append(day)
        return {
            **value,
            "days": converted,
        }


class PlanningJobCreateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    apply_to_itinerary: bool = False


class PlanningJobStartResponse(BaseModel):
    job_id: UUID
    status: PlanningStatus


class PlanningEventContract(BaseModel):
    sequence: int
    type: PlanningEventType
    stage: str | None = None
    message: str | None = None
    status: str | None = None
    tool_name: str | None = None
    provider: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class PlanningJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trip_id: UUID | None
    status: PlanningStatus
    progress: int
    events: list[PlanningEventContract]
    result: ItineraryDraftContract | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    tool_call_count: int = 0
    loop_count: int = 0
