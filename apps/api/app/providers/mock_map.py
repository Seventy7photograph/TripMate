# 文件说明：外部 Provider 适配：mock_map。
import math
from html import escape
from urllib.parse import quote, unquote

from app.providers.base import (
    GeoPoint,
    PlaceQuery,
    PlaceResult,
    RouteRequest,
    RouteResult,
    StaticMapImage,
    StaticMapRequest,
    fresh_source,
)

_CITY_ALIASES = {
    "重庆": "重庆",
    "chongqing": "重庆",
    "泉州": "泉州",
    "quanzhou": "泉州",
    "上海": "上海",
    "shanghai": "上海",
    "北京": "北京",
    "beijing": "北京",
    "大阪": "大阪",
    "osaka": "大阪",
}

_CITY_PLACES: dict[str, tuple[dict[str, object], ...]] = {
    "重庆": (
        {
            "id": "mock-hongyadong",
            "name": "洪崖洞民俗风貌区",
            "category": "风景名胜 / 旅游景点",
            "address": "渝中区 · 嘉陵江滨江路88号",
            "location": GeoPoint(106.579109, 29.562819),
        },
        {
            "id": "mock-jiefangbei",
            "name": "解放碑步行街",
            "category": "购物服务 / 特色商业街",
            "address": "渝中区 · 民权路",
            "location": GeoPoint(106.577178, 29.557456),
        },
        {
            "id": "mock-liziba",
            "name": "李子坝轻轨穿楼观景台",
            "category": "风景名胜 / 城市景观",
            "address": "渝中区 · 李子坝正街",
            "location": GeoPoint(106.532124, 29.550071),
        },
    ),
    "泉州": (
        {
            "id": "mock-quanzhou-kaiyuansi",
            "name": "泉州开元寺",
            "category": "风景名胜 / 宗教场所",
            "address": "鲤城区 · 西街176号",
            "location": GeoPoint(118.5835, 24.9139),
        },
        {
            "id": "mock-quanzhou-xijie",
            "name": "泉州西街",
            "category": "风景名胜 / 历史街区",
            "address": "鲤城区 · 西街",
            "location": GeoPoint(118.5857, 24.9146),
        },
        {
            "id": "mock-quanzhou-luoyangqiao",
            "name": "洛阳桥",
            "category": "风景名胜 / 古桥",
            "address": "洛江区 · 万安街道",
            "location": GeoPoint(118.6768, 24.9542),
        },
    ),
    "上海": (
        {
            "id": "mock-shanghai-bund",
            "name": "外滩",
            "category": "风景名胜 / 城市景观",
            "address": "黄浦区 · 中山东一路",
            "location": GeoPoint(121.4905, 31.2417),
        },
        {
            "id": "mock-shanghai-yuyuan",
            "name": "豫园",
            "category": "风景名胜 / 古典园林",
            "address": "黄浦区 · 福佑路168号",
            "location": GeoPoint(121.4921, 31.2270),
        },
        {
            "id": "mock-shanghai-wukang",
            "name": "武康路历史文化名街",
            "category": "风景名胜 / 城市漫步",
            "address": "徐汇区 · 武康路",
            "location": GeoPoint(121.4355, 31.2098),
        },
    ),
    "北京": (
        {
            "id": "mock-beijing-palace",
            "name": "故宫博物院",
            "category": "风景名胜 / 博物馆",
            "address": "东城区 · 景山前街4号",
            "location": GeoPoint(116.3970, 39.9180),
        },
        {
            "id": "mock-beijing-temple",
            "name": "天坛公园",
            "category": "风景名胜 / 历史建筑",
            "address": "东城区 · 天坛东里甲1号",
            "location": GeoPoint(116.4070, 39.8820),
        },
        {
            "id": "mock-beijing-shichahai",
            "name": "什刹海",
            "category": "风景名胜 / 历史街区",
            "address": "西城区 · 羊房胡同",
            "location": GeoPoint(116.3830, 39.9410),
        },
    ),
    "大阪": (
        {
            "id": "mock-osaka-castle",
            "name": "大阪城公园",
            "category": "风景名胜 / 历史建筑",
            "address": "中央区 · 大阪城1-1",
            "location": GeoPoint(135.5259, 34.6873),
        },
        {
            "id": "mock-osaka-dotonbori",
            "name": "道顿堀",
            "category": "美食 / 城市街区",
            "address": "中央区 · 道顿堀",
            "location": GeoPoint(135.5012, 34.6687),
        },
        {
            "id": "mock-osaka-umeda",
            "name": "梅田蓝天大厦",
            "category": "风景名胜 / 城市景观",
            "address": "北区 · 大淀中1-1-88",
            "location": GeoPoint(135.5009, 34.7025),
        },
    ),
}


def _mock_place(item: dict[str, object]) -> PlaceResult:
    provider_place_id = str(item["id"])
    return PlaceResult(
        provider_place_id=provider_place_id,
        name=str(item["name"]),
        category=str(item["category"]),
        address=str(item["address"]),
        location=item.get("location"),  # type: ignore[arg-type]
        tel=None,
        opening_hours=[],
        source=fresh_source(
            provider="mock",
            provider_place_id=provider_place_id,
            source_url=None,
            freshness="mock",
            confidence=1.0,
        ),
    )


def _resolve_city(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    for alias, city in _CITY_ALIASES.items():
        if alias in normalized:
            return city
    return None


def _generic_places(city: str) -> list[PlaceResult]:
    encoded = quote(city, safe="")
    labels = ("城市地标", "历史街区", "当地美食街")
    return [
        PlaceResult(
            provider_place_id=f"mock-generic-{encoded}-{index}",
            name=f"{city}{label}",
            category="Mock 示例类别",
            address=f"{city} · 示例地址",
            location=None,
            tel=None,
            opening_hours=[],
            source=fresh_source(
                provider="mock",
                provider_place_id=f"mock-generic-{encoded}-{index}",
                source_url=None,
                freshness="mock",
                confidence=1.0,
            ),
        )
        for index, label in enumerate(labels, start=1)
    ]


class MockMapProvider:
    name = "mock"

    async def search_places(self, query: PlaceQuery) -> list[PlaceResult]:
        keyword = query.keyword.strip().lower()
        city = _resolve_city(query.city) or _resolve_city(keyword)
        if city is not None:
            results = [_mock_place(item) for item in _CITY_PLACES[city]]
        else:
            known_places = [
                _mock_place(item)
                for places in _CITY_PLACES.values()
                for item in places
            ]
            results = [
                place
                for place in known_places
                if keyword
                and (
                    keyword in place.name.lower()
                    or keyword in (place.category or "").lower()
                    or keyword in (place.address or "").lower()
                )
            ]
            if not results:
                city_name = (query.city or query.keyword).strip() or "目的地"
                city_name = city_name.replace("景点", "").replace("美食", "").strip()
                results = _generic_places(city_name or "目的地")

        generic_terms = {"景点", "美食", "城市", "旅行"}
        cleaned = keyword
        for known_city in _CITY_ALIASES:
            cleaned = cleaned.replace(known_city, "")
        cleaned = cleaned.strip()
        if cleaned and cleaned not in generic_terms:
            filtered = [
                place
                for place in results
                if cleaned in place.name.lower()
                or cleaned in (place.category or "").lower()
                or cleaned in (place.address or "").lower()
            ]
            if filtered:
                results = filtered
        return results[: query.limit]

    async def get_place(self, provider_place_id: str) -> PlaceResult:
        for places in _CITY_PLACES.values():
            for item in places:
                if item["id"] == provider_place_id:
                    return _mock_place(item)
        if provider_place_id.startswith("mock-generic-"):
            parts = provider_place_id.rsplit("-", maxsplit=1)
            if len(parts) == 2 and parts[0].startswith("mock-generic-"):
                city = unquote(parts[0].removeprefix("mock-generic-"))
                for place in _generic_places(city):
                    if place.provider_place_id == provider_place_id:
                        return place
        raise KeyError(provider_place_id)

    async def geocode(self, address: str) -> GeoPoint:
        city = _resolve_city(address)
        if city is not None:
            location = _CITY_PLACES[city][0].get("location")
            if isinstance(location, GeoPoint):
                return location
        if "解放碑" in address:
            return GeoPoint(106.577178, 29.557456)
        raise KeyError(address)

    async def get_route(self, request: RouteRequest) -> RouteResult:
        distance = _haversine_m(request.origin, request.destination)
        speed_mps = {
            "driving": 10.0,
            "walking": 1.3,
            "bicycling": 4.0,
            "transit": 7.0,
            "bus": 6.0,
            "subway": 9.0,
            "high_speed_rail": 70.0,
            "train": 45.0,
            "flight": 180.0,
        }[request.mode]
        midpoint = GeoPoint(
            longitude=(request.origin.longitude + request.destination.longitude) / 2,
            latitude=(request.origin.latitude + request.destination.latitude) / 2,
        )
        polyline = ";".join(
            f"{point.longitude},{point.latitude}"
            for point in (request.origin, midpoint, request.destination)
        )
        return RouteResult(
            distance_m=round(distance),
            duration_s=max(1, round(distance / speed_mps)),
            polyline=polyline,
            source=fresh_source(
                provider="mock",
                provider_place_id=None,
                source_url=None,
                freshness="mock",
                confidence=1.0,
            ),
        )

    async def render_static_map(self, request: StaticMapRequest) -> StaticMapImage:
        width = request.width
        height = request.height
        points = [marker.point for marker in request.markers]
        for path in request.paths:
            points.extend(path)
        if not points:
            raise ValueError("mock map requires at least one marker")

        min_lng = min(point.longitude for point in points)
        max_lng = max(point.longitude for point in points)
        min_lat = min(point.latitude for point in points)
        max_lat = max(point.latitude for point in points)
        padding = 42

        def project(point: GeoPoint) -> tuple[float, float]:
            lng_span = max(max_lng - min_lng, 0.0001)
            lat_span = max(max_lat - min_lat, 0.0001)
            x = padding + (point.longitude - min_lng) / lng_span * (width - padding * 2)
            y = (
                height
                - padding
                - (point.latitude - min_lat) / lat_span * (height - padding * 2)
            )
            return x, y

        path_markup = ""
        for path in request.paths:
            coordinates = " ".join(
                f"{project(point)[0]:.1f},{project(point)[1]:.1f}" for point in path
            )
            path_markup += (
                f'<polyline points="{coordinates}" fill="none" '
                'stroke="#52634b" stroke-width="5" stroke-linecap="round" '
                'stroke-linejoin="round"/>'
            )

        marker_markup = ""
        legend_markup = ""
        for index, marker in enumerate(request.markers):
            x, y = project(marker.point)
            marker_markup += (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="13" fill="#dcece8" '
                'stroke="#52634b" stroke-width="2"/>'
                f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" '
                'font-family="Manrope, sans-serif" font-size="10" fill="#29423e">'
                f"{escape(marker.label[:1])}</text>"
            )
            legend_markup += (
                f'<text x="24" y="{height - 28 - index * 16}" '
                'font-family="Manrope, sans-serif" font-size="9" fill="#52634b">'
                f"{escape(marker.label[:1])} · {escape(marker.name)}</text>"
            )

        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="TripMate Mock Map">'
            f'<rect width="{width}" height="{height}" fill="#ece8de"/>'
            f'<text x="24" y="34" font-family="Manrope, sans-serif" font-size="12" '
            'font-weight="700" fill="#52634b">TripMate Mock Map</text>'
            f'<text x="24" y="52" font-family="Manrope, sans-serif" font-size="9" '
            'fill="#68706a">示意坐标预览，不包含真实道路数据</text>'
            f"{path_markup}{marker_markup}{legend_markup}</svg>"
        )
        return StaticMapImage(content=svg.encode(), media_type="image/svg+xml")


def _haversine_m(origin: GeoPoint, destination: GeoPoint) -> float:
    radius = 6_371_000
    lat1 = math.radians(origin.latitude)
    lat2 = math.radians(destination.latitude)
    delta_lat = lat2 - lat1
    delta_lng = math.radians(destination.longitude - origin.longitude)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
