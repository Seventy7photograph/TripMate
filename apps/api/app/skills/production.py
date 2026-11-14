# 文件说明：Skill 运行时：production。
"""TripMate 已审核 Skill 的受控可执行 handlers。"""

from datetime import UTC, datetime
from datetime import date as Date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.evidence.draft import EvidenceDraft
from app.evidence.freshness import resolve_freshness
from app.evidence.models import EvidenceRecord
from app.schemas.place import PlaceResponse
from app.skills.executor import SkillHandler
from app.skills.manifest import SkillManifest
from app.tools.altitude_tools import AltitudeOutput
from app.tools.attachment_tools import AttachmentUnderstandingOutput
from app.tools.budget_tools import BudgetToolInput, BudgetToolResult
from app.tools.context import ToolContext
from app.tools.evidence import write_evidence
from app.tools.matrix_tools import RouteMatrixOutput
from app.tools.memory_tools import AuthorizedMemoryOutput
from app.tools.place_fact_tools import PlaceFactOutput
from app.tools.place_tools import SearchPlacesOutput
from app.tools.registry import ToolRegistry
from app.tools.route_tools import GetRouteInput, RouteToolOutput
from app.tools.weather_tools import WeatherToolOutput


class DestinationResearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    types: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=5, ge=1, le=20)


class DestinationResearchOutput(BaseModel):
    places: list[PlaceResponse]
    searched_at: datetime


class RouteOptimizationInput(GetRouteInput):
    pass


class BudgetOptimizationInput(BudgetToolInput):
    pass


class EvidenceIssue(BaseModel):
    code: Literal["missing", "stale", "conflict", "unsupported_claim"]
    path: str
    message: str


class EvidenceVerificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[EvidenceRecord]
    now: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvidenceVerificationOutput(BaseModel):
    issues: list[EvidenceIssue]
    verified_count: int


class TripIntentRoutingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=50_000)
    available_skills: list[str] = Field(default_factory=list, max_length=20)


class TripIntentRoutingOutput(BaseModel):
    intent: Literal[
        "create_trip_plan",
        "revise_itinerary",
        "understand_attachment",
        "answer_travel_question",
        "recommend_options",
        "social_copywriting",
        "emergency_information",
        "clarify",
        "unsupported",
    ]
    confidence: float = Field(ge=0, le=1)
    selected_skills: list[str]
    allowed_tools: list[str]
    allowed_mcp_connectors: list[str]
    missing_information: list[str]
    token_budget: int
    tool_call_budget: int
    requires_confirmation: bool


class TravelMemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2_000)
    limit: int = Field(default=8, ge=1, le=20)


class SocialCopywritingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str = Field(min_length=1, max_length=120)
    platform: Literal["xiaohongshu", "wechat_moments", "weibo", "generic"]
    tone: Literal["quiet", "practical", "vivid"]
    confirmed_facts: list[str] = Field(default_factory=list, max_length=20)
    trip_days: int | None = Field(default=None, ge=1, le=60)


class SocialCopywritingOutput(BaseModel):
    title: str
    body: str
    hashtags: list[str]
    image_suggestions: list[str]
    evidence_links: list[str]
    warnings: list[str]
    facts_used: list[str] = Field(default_factory=list)
    auto_published: bool = False


class AttachmentUnderstandingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_ids: list[UUID] = Field(min_length=1, max_length=3)


class WeatherClothingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str = Field(min_length=1, max_length=120)
    date: Date


class WeatherClothingOutput(BaseModel):
    city: str
    date: Date
    condition: str
    temperature_max_c: int | None
    temperature_min_c: int | None
    precipitation_probability: int | None
    clothing_advice: list[str]
    outdoor_risk: Literal["low", "moderate", "high"]
    evidence_ids: list[str]


class FoodPlanningInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meal: Literal["breakfast", "lunch", "dinner"]
    city: str = Field(min_length=1, max_length=120)
    dietary: list[str] = Field(default_factory=list, max_length=12)
    budget_minor_per_person: int | None = Field(default=None, ge=0)
    limit: int = Field(default=2, ge=1, le=3)
    date: Date = Field(default_factory=Date.today)


class FoodMealOption(BaseModel):
    place_id: str
    name: str
    category: str | None
    address: str | None
    opening_hours: list[str]
    opening_hours_status: Literal["known", "unknown"]
    reference_price: str | None
    evidence_ids: list[UUID]


class FoodPlanningOutput(BaseModel):
    meal: Literal["breakfast", "lunch", "dinner"]
    city: str
    meals: list[FoodMealOption]
    warnings: list[str]
    evidence_free_text: str
    evidence_ids: list[UUID]


class LodgingAreaSelectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str = Field(min_length=1, max_length=120)
    preferences: list[str] = Field(default_factory=list, max_length=12)
    budget_minor_per_night: int | None = Field(default=None, ge=0)
    limit: int = Field(default=3, ge=2, le=3)


class LodgingAreaOption(BaseModel):
    anchor_place_id: str
    name: str
    address: str | None
    category: str | None
    evidence_ids: list[UUID]


class LodgingAreaSelectionOutput(BaseModel):
    city: str
    areas: list[LodgingAreaOption]
    availability_notice: str
    warnings: list[str]
    evidence_ids: list[UUID]


class SafetyBriefingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dates: list[Date] = Field(min_length=1, max_length=7)
    party: list[str] = Field(default_factory=list, max_length=12)
    city: str | None = Field(default=None, max_length=120)
    altitude_m: float | None = Field(default=None, ge=-500, le=9_000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class SafetyBriefingOutput(BaseModel):
    level: Literal["low", "moderate", "warning", "high"]
    reminders: list[str]
    weather_notes: list[str]
    disclaimer: str
    evidence_ids: list[UUID]


def production_skill_handlers(
    tools: ToolRegistry,
    context: ToolContext,
) -> dict[str, SkillHandler]:
    """构建已审核 handler 映射；Skill 只能访问传入的 ToolRegistry。"""
    return {
        "destination-research": _destination_research(tools),
        "route-optimization": _route_optimization(tools),
        "budget-optimization": _budget_optimization(tools),
        "evidence-verification": _evidence_verification,
        "trip-intent-routing": _trip_intent_routing,
        "travel-memory": _travel_memory(tools),
        "social-copywriting": _social_copywriting,
        "weather-and-clothing": _weather_and_clothing(tools),
        "food-planning": _food_planning(tools),
        "lodging-area-selection": _lodging_area_selection(tools),
        "safety-briefing": _safety_briefing(tools),
        "attachment-understanding": _attachment_understanding(tools),
    }


def _destination_research(tools: ToolRegistry) -> SkillHandler:
    async def handler(
        _: SkillManifest,
        tool_context: ToolContext,
        input_data: BaseModel,
    ) -> BaseModel:
        request = DestinationResearchInput.model_validate(input_data)
        result = SearchPlacesOutput.model_validate(
            await tools.invoke(
                tool_context,
                "search_places",
                {
                    "keyword": request.query,
                    "city": request.city,
                    "types": request.types,
                    "limit": request.limit,
                },
            )
        )
        return DestinationResearchOutput(
            places=result.results,
            searched_at=datetime.now(UTC),
        )

    return handler


def _route_optimization(tools: ToolRegistry) -> SkillHandler:
    async def handler(
        _: SkillManifest,
        tool_context: ToolContext,
        input_data: BaseModel,
    ) -> BaseModel:
        request = RouteOptimizationInput.model_validate(input_data)
        return RouteToolOutput.model_validate(
            await tools.invoke(
                tool_context,
                "get_route",
                request.model_dump(mode="json"),
            )
        )

    return handler


def _budget_optimization(tools: ToolRegistry) -> SkillHandler:
    async def handler(
        _: SkillManifest,
        tool_context: ToolContext,
        input_data: BaseModel,
    ) -> BaseModel:
        request = BudgetOptimizationInput.model_validate(input_data)
        return BudgetToolResult.model_validate(
            await tools.invoke(
                tool_context,
                "calculate_budget",
                request.model_dump(),
            )
        )

    return handler


async def _evidence_verification(
    _: SkillManifest,
    __: ToolContext,
    input_data: BaseModel,
) -> BaseModel:
    """只验证传入 Evidence，不访问网络或数据库。"""
    request = EvidenceVerificationInput.model_validate(input_data)
    issues: list[EvidenceIssue] = []
    verified_count = 0
    for index, record in enumerate(request.records):
        freshness = resolve_freshness(
            source_freshness=record.freshness,
            valid_until=record.valid_until,
            now=request.now,
        )
        if freshness == "stale":
            issues.append(
                EvidenceIssue(
                    code="stale",
                    path=f"records.{index}",
                    message="Evidence has expired and cannot be treated as live.",
                )
            )
            continue
        if not record.provider.strip():
            issues.append(
                EvidenceIssue(
                    code="missing",
                    path=f"records.{index}.provider",
                    message="Evidence provider is missing.",
                )
            )
            continue
        verified_count += 1
    return EvidenceVerificationOutput(
        issues=issues,
        verified_count=verified_count,
    )


async def _trip_intent_routing(
    _: SkillManifest,
    __: ToolContext,
    input_data: BaseModel,
) -> BaseModel:
    """独立路由 Skill 使用的保守兜底路由器。"""
    request = TripIntentRoutingInput.model_validate(input_data)
    text = request.text.strip().lower()
    if text in {"你好", "您好", "嗨", "hi", "hello"}:
        return TripIntentRoutingOutput(
            intent="clarify",
            confidence=0.98,
            selected_skills=[],
            allowed_tools=[],
            allowed_mcp_connectors=[],
            missing_information=[],
            token_budget=1200,
            tool_call_budget=0,
            requires_confirmation=False,
        )
    if any(term in text for term in ("写代码", "python", "股票", "数学题")):
        return TripIntentRoutingOutput(
            intent="unsupported",
            confidence=0.99,
            selected_skills=[],
            allowed_tools=[],
            allowed_mcp_connectors=[],
            missing_information=[],
            token_budget=1200,
            tool_call_budget=0,
            requires_confirmation=False,
        )
    if any(term in text for term in ("附件", "截图", "图片", "文档")):
        selected = ["attachment-understanding"]
        return TripIntentRoutingOutput(
            intent="understand_attachment",
            confidence=0.86,
            selected_skills=[
                skill
                for skill in selected
                if skill in request.available_skills
            ],
            allowed_tools=["extract_attachment"],
            allowed_mcp_connectors=[],
            missing_information=[],
            token_budget=3000,
            tool_call_budget=2,
            requires_confirmation=False,
        )
    if any(term in text for term in ("小红书", "朋友圈", "微博", "文案")):
        selected = ["social-copywriting"]
        return TripIntentRoutingOutput(
            intent="social_copywriting",
            confidence=0.86,
            selected_skills=[
                skill
                for skill in selected
                if skill in request.available_skills
            ],
            allowed_tools=[],
            allowed_mcp_connectors=[],
            missing_information=[],
            token_budget=3000,
            tool_call_budget=0,
            requires_confirmation=True,
        )
    if any(term in text for term in ("偏好", "记忆", "不吃", "喜欢住")):
        selected = ["travel-memory"]
        return TripIntentRoutingOutput(
            intent="answer_travel_question",
            confidence=0.8,
            selected_skills=[
                skill
                for skill in selected
                if skill in request.available_skills
            ],
            allowed_tools=["get_authorized_memory_context"],
            allowed_mcp_connectors=[],
            missing_information=[],
            token_budget=2000,
            tool_call_budget=2,
            requires_confirmation=False,
        )
    if any(term in text for term in ("规划", "安排", "行程", "去", "出发")):
        return TripIntentRoutingOutput(
            intent="create_trip_plan",
            confidence=0.85,
            selected_skills=[],
            allowed_tools=[],
            allowed_mcp_connectors=[],
            missing_information=[],
            token_budget=8000,
            tool_call_budget=8,
            requires_confirmation=True,
        )
    return TripIntentRoutingOutput(
        intent="answer_travel_question",
        confidence=0.72,
        selected_skills=[],
        allowed_tools=[],
        allowed_mcp_connectors=[],
        missing_information=[],
        token_budget=4000,
        tool_call_budget=4,
        requires_confirmation=False,
    )


def _travel_memory(tools: ToolRegistry) -> SkillHandler:
    async def handler(
        _: SkillManifest,
        tool_context: ToolContext,
        input_data: BaseModel,
    ) -> BaseModel:
        request = TravelMemoryInput.model_validate(input_data)
        return AuthorizedMemoryOutput.model_validate(
            await tools.invoke(
                tool_context,
                "get_authorized_memory_context",
                request.model_dump(),
            )
        )

    return handler


async def _social_copywriting(
    _: SkillManifest,
    __: ToolContext,
    input_data: BaseModel,
) -> BaseModel:
    """只根据已确认事实起草文案，不自动发布，也不声称亲身体验。"""
    request = SocialCopywritingInput.model_validate(input_data)
    fact_text = "；".join(request.confirmed_facts[:6])
    duration = f"{request.trip_days} 天" if request.trip_days else "这段"
    platform_labels = {
        "xiaohongshu": "小红书",
        "wechat_moments": "朋友圈",
        "weibo": "微博",
        "generic": "通用",
    }
    tone_openers = {
        "quiet": "把脚步放慢一点",
        "practical": "这份行程以可执行为先",
        "vivid": "这趟旅程值得被记住",
    }
    body_parts = [
        f"{tone_openers[request.tone]}，{request.destination}{duration}旅行可以这样安排。",
        fact_text or "目前还没有已确认的行程事实，请先补充地点、日期或安排。",
        "以上是基于已确认信息的整理，未标注的信息请以官方渠道为准。",
    ]
    return SocialCopywritingOutput(
        title=f"{request.destination}｜{platform_labels[request.platform]}旅行记录",
        body="\n".join(body_parts),
        hashtags=[
            f"#{request.destination}旅行",
            "#行程规划",
            f"#{platform_labels[request.platform]}",
        ],
        image_suggestions=[
            f"{request.destination}地标或街景照片",
            "已确认行程中的地点照片",
        ],
        evidence_links=[],
        warnings=(
            ["未提供已确认事实，正文不包含价格、营业时间或个人体验。"]
            if not request.confirmed_facts
            else ["发布前请确认隐私信息，系统不会自动发布。"]
        ),
        facts_used=list(request.confirmed_facts[:6]),
        auto_published=False,
    )


def _attachment_understanding(tools: ToolRegistry) -> SkillHandler:
    async def handler(
        _: SkillManifest,
        tool_context: ToolContext,
        input_data: BaseModel,
    ) -> BaseModel:
        request = AttachmentUnderstandingInput.model_validate(input_data)
        return AttachmentUnderstandingOutput.model_validate(
            await tools.invoke(
                tool_context,
                "extract_attachment",
                request.model_dump(mode="json"),
            )
        )

    return handler


def _weather_and_clothing(tools: ToolRegistry) -> SkillHandler:
    async def handler(
        _: SkillManifest,
        tool_context: ToolContext,
        input_data: BaseModel,
    ) -> BaseModel:
        request = WeatherClothingInput.model_validate(input_data)
        weather = WeatherToolOutput.model_validate(
            await tools.invoke(
                tool_context,
                "get_weather",
                {
                    "city": request.city,
                    "date": request.date.isoformat(),
                },
            )
        )
        clothing: list[str] = []
        if (
            weather.temperature_min_c is not None
            and weather.temperature_min_c <= 10
        ):
            clothing.append("早晚温差明显，建议携带外套或保暖层。")
        if (
            weather.temperature_max_c is not None
            and weather.temperature_max_c >= 28
        ):
            clothing.append("日间偏热，建议透气衣物和防晒。")
        if (
            weather.precipitation_probability is not None
            and weather.precipitation_probability >= 50
        ):
            clothing.append("降水概率较高，建议携带雨具。")
        if not clothing:
            clothing.append("当前预报无极端温度提示，按季节正常着装。")
        risk: Literal["low", "moderate", "high"] = "low"
        if (
            weather.precipitation_probability is not None
            and weather.precipitation_probability >= 70
        ):
            risk = "high"
        elif clothing != ["当前预报无极端温度提示，按季节正常着装。"]:
            risk = "moderate"
        return WeatherClothingOutput(
            city=weather.city,
            date=weather.date,
            condition=weather.condition,
            temperature_max_c=weather.temperature_max_c,
            temperature_min_c=weather.temperature_min_c,
            precipitation_probability=weather.precipitation_probability,
            clothing_advice=clothing,
            outdoor_risk=risk,
            evidence_ids=[str(weather.evidence_id)],
        )

    return handler


def _food_planning(tools: ToolRegistry) -> SkillHandler:
    async def handler(
        _: SkillManifest,
        tool_context: ToolContext,
        input_data: BaseModel,
    ) -> BaseModel:
        request = FoodPlanningInput.model_validate(input_data)
        meal_label = {
            "breakfast": "早餐",
            "lunch": "午餐",
            "dinner": "晚餐",
        }[request.meal]
        places = SearchPlacesOutput.model_validate(
            await tools.invoke(
                tool_context,
                "search_places",
                {
                    "keyword": f"{request.city} {meal_label}",
                    "city": request.city,
                    "types": "餐饮服务",
                    "limit": request.limit,
                },
            )
        ).results
        meals: list[FoodMealOption] = []
        warnings: list[str] = []
        evidence_ids: list[UUID] = []
        for place in places:
            facts = PlaceFactOutput.model_validate(
                await tools.invoke(
                    tool_context,
                    "get_place_facts",
                    {
                        "place_id": place.provider_place_id,
                        "date": request.date.isoformat(),
                    },
                )
            )
            evidence_ids.extend(facts.evidence_ids)
            opening_status: Literal["known", "unknown"] = (
                "known"
                if facts.opening_hours_status == "known"
                else "unknown"
            )
            meals.append(
                FoodMealOption(
                    place_id=place.provider_place_id,
                    name=place.name,
                    category=place.category,
                    address=place.address,
                    opening_hours=facts.opening_hours,
                    opening_hours_status=opening_status,
                    reference_price=facts.reference_price,
                    evidence_ids=facts.evidence_ids,
                )
            )
        if request.dietary:
            warnings.append(
                "忌口和过敏信息需要向餐厅再次确认："
                + "、".join(request.dietary)
            )
        warnings.append("人均价格未确认时不得视为实时报价。")
        return FoodPlanningOutput(
            meal=request.meal,
            city=request.city,
            meals=meals,
            warnings=list(dict.fromkeys(warnings)),
            evidence_free_text=(
                "营业时间和参考价格必须以地点事实 Evidence 为准；"
                "未确认信息请以现场为准。"
            ),
            evidence_ids=list(dict.fromkeys(evidence_ids)),
        )

    return handler


def _lodging_area_selection(tools: ToolRegistry) -> SkillHandler:
    async def handler(
        _: SkillManifest,
        tool_context: ToolContext,
        input_data: BaseModel,
    ) -> BaseModel:
        request = LodgingAreaSelectionInput.model_validate(input_data)
        places = SearchPlacesOutput.model_validate(
            await tools.invoke(
                tool_context,
                "search_places",
                {
                    "keyword": f"{request.city} 地铁站 住宿区域",
                    "city": request.city,
                    "types": "交通设施服务",
                    "limit": request.limit,
                },
            )
        ).results[: request.limit]
        if len(places) < 2:
            raise ValueError("lodging area comparison requires two anchors")
        matrix = RouteMatrixOutput.model_validate(
            await tools.invoke(
                tool_context,
                "get_route_matrix",
                {
                    "place_ids": [
                        place.provider_place_id for place in places
                    ],
                    "mode": "walking",
                },
            )
        )
        evidence_ids = list(dict.fromkeys(matrix.evidence_ids))
        return LodgingAreaSelectionOutput(
            city=request.city,
            areas=[
                LodgingAreaOption(
                    anchor_place_id=place.provider_place_id,
                    name=place.name,
                    address=place.address,
                    category=place.category,
                    evidence_ids=evidence_ids,
                )
                for place in places
            ],
            availability_notice=(
                "仅比较区域与交通，不提供酒店房态或可订承诺。"
            ),
            warnings=[
                "预算仅用于筛选区域，不代表酒店实时价格。",
                *(
                    ["偏好需要结合步行、交通和夜间环境进一步确认。"]
                    if request.preferences
                    else []
                ),
            ],
            evidence_ids=evidence_ids,
        )

    return handler


def _safety_briefing(tools: ToolRegistry) -> SkillHandler:
    async def handler(
        _: SkillManifest,
        tool_context: ToolContext,
        input_data: BaseModel,
    ) -> BaseModel:
        request = SafetyBriefingInput.model_validate(input_data)
        reminders: list[str] = []
        weather_notes: list[str] = []
        evidence_ids: list[UUID] = []
        altitude = request.altitude_m
        if request.city:
            for travel_date in request.dates[:3]:
                weather = WeatherToolOutput.model_validate(
                    await tools.invoke(
                        tool_context,
                        "get_weather",
                        {
                            "city": request.city,
                            "date": travel_date.isoformat(),
                        },
                    )
                )
                evidence_ids.append(weather.evidence_id)
                weather_notes.append(
                    f"{travel_date.isoformat()} {weather.condition}，"
                    f"{weather.temperature_min_c or '未知'}~"
                    f"{weather.temperature_max_c or '未知'}°C"
                )
                if (
                    weather.precipitation_probability is not None
                    and weather.precipitation_probability >= 60
                ):
                    reminders.append("降水概率较高，准备雨具和防滑鞋。")
        if (
            request.latitude is not None
            and request.longitude is not None
        ):
            altitude_output = AltitudeOutput.model_validate(
                await tools.invoke(
                    tool_context,
                    "get_altitude",
                    {
                        "latitude": request.latitude,
                        "longitude": request.longitude,
                    },
                )
            )
            altitude = altitude_output.altitude_m
            evidence_ids.append(altitude_output.evidence_id)
        elif request.altitude_m is not None:
            evidence_id = await write_evidence(
                tool_context,
                EvidenceDraft(
                    fact_type="safety",
                    provider="user-input",
                    provider_record_id=(
                        f"safety:altitude:{request.altitude_m}"
                    ),
                    fetched_at=datetime.now(UTC),
                    confidence=1.0,
                    freshness="live",
                    value={"altitude_m": request.altitude_m},
                ),
            )
            evidence_ids.append(evidence_id)

        level: Literal["low", "moderate", "warning", "high"] = "low"
        if altitude is not None and altitude >= 3500:
            level = "high"
            reminders.append("高海拔环境风险较高，减少剧烈活动并预留适应时间。")
        elif altitude is not None and altitude >= 2500:
            level = "warning"
            reminders.append(
                "海拔超过 2500 米，注意高海拔反应并准备保暖和补水。"
            )
        if reminders and level == "low":
            level = "moderate"
        vulnerable = {
            item
            for item in request.party
            if item in {"child", "older_adult", "pregnant", "chronic_condition"}
        }
        if vulnerable and level != "low":
            reminders.append("同行者包含需要额外关注的人群，请降低活动强度。")
        if not reminders:
            reminders.append("未发现已提供事实中的高风险信号，仍需关注天气变化。")
        return SafetyBriefingOutput(
            level=level,
            reminders=list(dict.fromkeys(reminders)),
            weather_notes=weather_notes,
            disclaimer="安全提示不替代医疗意见；出现严重不适请及时就医。",
            evidence_ids=list(dict.fromkeys(evidence_ids)),
        )

    return handler
