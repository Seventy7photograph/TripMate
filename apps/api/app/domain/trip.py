# 文件说明：领域对象：trip。
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, cast
from uuid import UUID

from app.domain.transport import TransportStrategy

TripStatus = Literal["draft", "planning", "ready", "archived"]
TripPace = Literal["relaxed", "balanced", "intensive"]


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


@dataclass(frozen=True, slots=True)
class TripBrief:
    destination: str
    origin: str | None
    start_date: date
    end_date: date
    party_size: int
    budget_minor: int | None
    currency: str
    interests: list[str]
    pace: TripPace
    transport_preferences: list[str]
    transport_strategy: TransportStrategy
    lodging_preferences: list[str]
    must_visit: list[str]
    avoid: list[str]
    constraints: list[str]

    def to_record(self) -> dict[str, object]:
        return {
            "destination": self.destination,
            "origin": self.origin,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "party_size": self.party_size,
            "budget_minor": self.budget_minor,
            "currency": self.currency,
            "interests": self.interests,
            "pace": self.pace,
            "transport_preferences": self.transport_preferences,
            "transport_strategy": self.transport_strategy.model_dump(mode="json"),
            "lodging_preferences": self.lodging_preferences,
            "must_visit": self.must_visit,
            "avoid": self.avoid,
            "constraints": self.constraints,
        }

    @classmethod
    def from_record(cls, record: dict[str, object]) -> "TripBrief":
        return cls(
            destination=str(record["destination"]),
            origin=_optional_string(record.get("origin")),
            start_date=date.fromisoformat(str(record["start_date"])),
            end_date=date.fromisoformat(str(record["end_date"])),
            party_size=int(cast(int | str, record["party_size"])),
            budget_minor=(
                int(cast(int | str, record["budget_minor"]))
                if record.get("budget_minor") is not None
                else None
            ),
            currency=str(record["currency"]),
            interests=_string_list(record.get("interests")),
            pace=cast(TripPace, str(record["pace"])),
            transport_preferences=_string_list(record.get("transport_preferences")),
            transport_strategy=TransportStrategy.model_validate(
                record.get("transport_strategy") or {}
            ),
            lodging_preferences=_string_list(record.get("lodging_preferences")),
            must_visit=_string_list(record.get("must_visit")),
            avoid=_string_list(record.get("avoid")),
            constraints=_string_list(record.get("constraints")),
        )


@dataclass(frozen=True, slots=True)
class Trip:
    id: UUID
    owner_id: UUID
    status: TripStatus
    version: int
    brief: TripBrief
    created_at: datetime
    updated_at: datetime
