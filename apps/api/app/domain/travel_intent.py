# 文件说明：旅行意图的确定性语义规则，不依赖 Provider 或框架。
"""识别明确的一日游、城市漫步与目的地规划表达。"""

import re
from dataclasses import dataclass

TRIP_ACTIVITY_TERMS = (
    "一日游",
    "1日游",
    "一天游",
    "两日游",
    "2日游",
    "周末游",
    "周边游",
    "citywalk",
    "城市漫步",
    "城市漫游",
)
_DESTINATION_ACTIVITY_SUFFIX = (
    r"(?:一日游|1日游|一天游|两日游|2日游|"
    r"周末游|周边游|citywalk|城市漫步|城市漫游)"
)
_DESTINATION_BOUNDARY = (
    r"(?:一日游|1日游|一天游|两日游|2日游|周末游|周边游|"
    r"citywalk|城市漫步|城市漫游|怎么走|怎么去|如何到|如何走|"
    r"穿什么|穿啥|有什么|吃什么|好玩|值得|开放|门票|需要|签证|"
    r"入境|天气|预算|费用|花费|高反|安全|风险|方便|区域|哪个|"
    r"哪里|住宿|酒店|民宿|交通|路线|停车|地铁|公交|自驾|玩|吃|"
    r"看|住|逛)"
)
_NON_TRAVEL_TERMS = (
    "python",
    "javascript",
    "写代码",
    "编程",
    "股票",
    "基金",
    "彩票",
    "数学题",
    "物理题",
    "化学题",
    "医疗诊断",
    "写论文",
)
_EXPLICIT_PLANNING_TERMS = (
    "规划",
    "安排",
    "设计",
    "定制",
    "行程",
    *TRIP_ACTIVITY_TERMS,
)
_GENERIC_TRAVEL_TERMS = (
    "旅行",
    "旅游",
    "目的地",
    "攻略",
    "自由行",
    "度假",
    "出发",
)
_TOPIC_TERMS = (
    (
        "food",
        ("美食", "好吃", "小吃", "餐厅", "必吃", "饮食", "吃什么"),
    ),
    (
        "attractions",
        (
            "景点",
            "古城",
            "博物馆",
            "寺庙",
            "寺",
            "值得看",
            "怎么玩",
            "好玩",
            "开放",
            "门票",
        ),
    ),
    (
        "route",
        ("怎么走", "怎么去", "如何到", "如何走", "路线", "导航", "车程"),
    ),
    (
        "transport",
        (
            "交通",
            "自驾",
            "地铁",
            "公交",
            "停车",
            "步行",
            "高铁",
            "火车",
            "飞机",
            "机票",
            "打车",
            "租车",
        ),
    ),
    ("lodging", ("住宿", "酒店", "民宿", "住哪", "区域")),
    ("weather", ("天气", "穿衣", "穿什么", "穿啥", "季节", "气温")),
    ("budget", ("预算", "费用", "花费", "多少钱", "够吗", "超支")),
    ("policy", ("签证", "入境", "政策", "免签", "护照")),
    ("safety", ("高反", "安全", "风险", "危险", "急救")),
)


@dataclass(frozen=True, slots=True)
class TravelSignal:
    in_scope: bool
    topic: str | None
    destination: str | None
    confidence: float


def is_obviously_non_travel(message: str) -> bool:
    searchable = message.casefold()
    return any(term in searchable for term in _NON_TRAVEL_TERMS)


def classify_travel_signals(message: str) -> TravelSignal:
    normalized = message.strip()
    if not normalized or is_obviously_non_travel(normalized):
        return TravelSignal(
            in_scope=False,
            topic=None,
            destination=None,
            confidence=0.99,
        )

    searchable = normalized.casefold()
    destination = extract_trip_destination(normalized)
    if _is_follow_up_planning_update(searchable) or any(
        term in searchable for term in _EXPLICIT_PLANNING_TERMS
    ):
        return _travel_signal("planning", destination, confidence=0.94)

    if _has_concrete_trip_constraints(normalized, destination):
        return _travel_signal("planning", destination, confidence=0.92)

    for topic, terms in _TOPIC_TERMS:
        if any(term in searchable for term in terms):
            return _travel_signal(topic, destination)

    if any(term in searchable for term in _GENERIC_TRAVEL_TERMS):
        return _travel_signal("destination", destination, confidence=0.72)

    if destination:
        return _travel_signal("destination", destination, confidence=0.8)

    return TravelSignal(
        in_scope=False,
        topic=None,
        destination=None,
        confidence=0.78,
    )


def _travel_signal(
    topic: str,
    destination: str | None,
    *,
    confidence: float = 0.9,
) -> TravelSignal:
    return TravelSignal(
        in_scope=True,
        topic=topic,
        destination=destination,
        confidence=confidence if destination else confidence - 0.08,
    )


def _is_follow_up_planning_update(message: str) -> bool:
    return bool(
        re.search(
            r"(?:改成|改到|换成|调整为|预算(?:加|提高|调整))",
            message,
        )
    )


def _has_concrete_trip_constraints(
    message: str,
    destination: str | None,
) -> bool:
    has_date = bool(re.search(r"\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日", message))
    has_party_size = bool(
        re.search(
            r"(?<![\d一二两三四五六七八九十])"
            r"(?:\d{1,2}|[一二两三四五六七八九十])(?:个)?人",
            message,
        )
    )
    return has_date or (destination is not None and has_party_size)


def extract_trip_destination(message: str) -> str | None:
    route_match = re.search(
        r"(?:去|到|前往)(?P<destination>[\u4e00-\u9fa5]{2,12}?)"
        rf"(?=\s*{_DESTINATION_BOUNDARY}|[，,。；;\s]|$|预算|\d|"
        r"[一二两三四五六七八九十]个?人|"
        r"旅行|旅游|游玩|玩|吃|逛|看|住|出差|探亲)",
        message,
        flags=re.IGNORECASE,
    )
    if route_match is not None:
        return route_match.group("destination")

    planned_activity_match = re.search(
        r"(?:规划|安排|设计|定制)"
        r"(?:一次|一趟|一个|一场|本次)?"
        rf"(?P<destination>[\u4e00-\u9fa5]{{2,8}}?)"
        rf"\s*{_DESTINATION_ACTIVITY_SUFFIX}",
        message,
        flags=re.IGNORECASE,
    )
    if planned_activity_match is not None:
        return planned_activity_match.group("destination")

    planned_duration_match = re.search(
        r"(?:规划|安排|设计|定制)"
        r"(?:一次|一趟|一个|一场|本次)?"
        r"(?P<destination>[\u4e00-\u9fa5]{2,8}?)"
        r"(?=\s*(?:\d+|[一二两三四五六七八九十]+)\s*(?:天|日|晚))",
        message,
        flags=re.IGNORECASE,
    )
    if planned_duration_match is not None:
        return planned_duration_match.group("destination")

    lodging_match = re.search(
        r"住(?:宿|在)?(?P<destination>[\u4e00-\u9fa5]{2,8}?)"
        r"(?=哪个|哪里|哪|附近|区域|方便|酒店|民宿|$)",
        message,
    )
    if lodging_match is not None:
        return lodging_match.group("destination")

    standalone_activity_match = re.search(
        r"(?:^|[，,。；;\s])"
        rf"(?P<destination>[\u4e00-\u9fa5]{{2,8}}?)"
        rf"\s*{_DESTINATION_ACTIVITY_SUFFIX}",
        message,
        flags=re.IGNORECASE,
    )
    if standalone_activity_match is not None:
        return standalone_activity_match.group("destination")

    leading_destination_match = re.search(
        r"^(?:请问|请帮我|我想|想|在)?"
        r"(?P<destination>[\u4e00-\u9fa5]{2,8}?)"
        r"(?=有什么|怎么玩|怎么安排|值得|开放|今天|明天|后天|"
        r"三天|四天|五天|\d+\s*天|预算|费用|花费|天气|穿什么|"
        r"签证|入境|需要|到|去|前往|高反|安全|风险|酒店|住宿|"
        r"区域|方便)",
        message,
    )
    if leading_destination_match is not None:
        return leading_destination_match.group("destination")
    return None


def is_explicit_trip_plan_request(message: str) -> bool:
    searchable = message.casefold()
    return extract_trip_destination(message) is not None and any(
        term in searchable for term in TRIP_ACTIVITY_TERMS
    )


def is_citywalk_message(message: str) -> bool:
    searchable = message.casefold()
    return any(term in searchable for term in ("citywalk", "城市漫步", "城市漫游"))
