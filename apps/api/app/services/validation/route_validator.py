# 文件说明：确定性校验器：route_validator。
from typing import Protocol

from app.providers.base import (
    ProviderError,
    point_from_record,
)
from app.schemas.ai import ItineraryDraftContract, ValidationIssueContract
from app.tools.route_tools import RouteToolInput, RouteToolOutput


class RouteLookup(Protocol):
    async def get(self, request: RouteToolInput) -> RouteToolOutput: ...


async def validate_routes(
    draft: ItineraryDraftContract,
    *,
    candidates: list[dict[str, object]],
    route_lookup: RouteLookup,
) -> list[ValidationIssueContract]:
    candidate_by_id = {
        str(candidate["provider_place_id"]): candidate
        for candidate in candidates
    }
    issues: list[ValidationIssueContract] = []
    for day in draft.days:
        for origin, destination in zip(day.stops, day.stops[1:], strict=False):
            origin_record = candidate_by_id.get(origin.place_id)
            destination_record = candidate_by_id.get(destination.place_id)
            if origin_record is None or destination_record is None:
                issues.append(
                    ValidationIssueContract(
                        code="unknown_place",
                        severity="error",
                        path=f"{day.id}.{origin.place_id}",
                        message="行程包含候选集之外的地点",
                    )
                )
                continue
            origin_location = point_from_record(origin_record.get("location"))
            destination_location = point_from_record(
                destination_record.get("location")
            )
            if origin_location is None or destination_location is None:
                issues.append(
                    ValidationIssueContract(
                        code="missing_coordinates",
                        severity="error",
                        path=f"{day.id}.{origin.place_id}",
                        message="地点缺少坐标，无法计算路线",
                    )
                )
                continue
            try:
                route = await route_lookup.get(
                    RouteToolInput(
                        origin=origin_location,
                        destination=destination_location,
                        mode="driving",
                    )
                )
            except ProviderError:
                issues.append(
                    ValidationIssueContract(
                        code="route_unavailable",
                        severity="warning",
                        path=f"{day.id}.{destination.place_id}",
                        message="路线 Provider 暂时不可用",
                        repair_hint=None,
                    )
                )
                continue
            if route.duration_s > 4 * 60 * 60:
                issues.append(
                    ValidationIssueContract(
                        code="commute_too_long",
                        severity="warning",
                        path=f"{day.id}.{destination.place_id}",
                        message="相邻地点通勤超过 4 小时",
                        repair_hint="调整地点顺序或移除可选地点",
                    )
                )
    return issues
