# 文件说明：外部 Provider 适配：amap。
import asyncio
import json
from datetime import UTC, datetime
from typing import cast

import httpx

from app.providers.base import (
    GeoPoint,
    PlaceQuery,
    PlaceResult,
    ProviderConfigurationError,
    ProviderModeUnsupportedError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RouteRequest,
    RouteResult,
    StaticMapImage,
    StaticMapRequest,
    fresh_source,
    normalize_category_text,
)

_RATE_LIMIT_INFO_CODES = {"10004", "10019", "10020", "10021", "10029", "10044"}


class AmapMapProvider:
    name = "amap"

    def __init__(
        self,
        *,
        key: str,
        base_url: str = "https://restapi.amap.com",
        timeout_seconds: float = 5,
        max_retries: int = 2,
        retry_delay_seconds: float = 0.2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not key.strip():
            raise ProviderConfigurationError("AMAP_WEB_SERVICE_KEY is required")
        self._key = key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search_places(self, query: PlaceQuery) -> list[PlaceResult]:
        params: dict[str, str | int | float | bool | None] = {
            "keywords": query.keyword,
            "offset": min(max(query.limit, 1), 25),
            "page": 1,
            "extensions": "all",
        }
        if query.city:
            params["city"] = query.city
        if query.types:
            params["types"] = query.types
        payload = await self._request("/v3/place/text", params)
        pois = cast(list[dict[str, object]], payload.get("pois", []))
        return [self._parse_place(poi) for poi in pois if poi.get("id") and poi.get("name")]

    async def get_place(self, provider_place_id: str) -> PlaceResult:
        payload = await self._request(
            "/v3/place/detail",
            {"id": provider_place_id, "extensions": "all"},
        )
        pois = cast(list[dict[str, object]], payload.get("pois", []))
        if not pois:
            raise ProviderResponseError("AMap place detail returned no POI")
        return self._parse_place(pois[0])

    async def search_nearby(
        self,
        *,
        location: GeoPoint,
        radius_m: int,
        types: list[str],
        limit: int,
    ) -> list[PlaceResult]:
        params: dict[str, str | int | float | bool | None] = {
            "location": self._format_point(location),
            "radius": radius_m,
            "offset": min(max(limit, 1), 25),
            "page": 1,
            "extensions": "all",
        }
        if types:
            params["types"] = "|".join(types)
        payload = await self._request("/v3/place/around", params)
        pois = cast(list[dict[str, object]], payload.get("pois", []))
        return [
            self._parse_place(poi)
            for poi in pois
            if poi.get("id") and poi.get("name")
        ]

    async def geocode(self, address: str) -> GeoPoint:
        payload = await self._request("/v3/geocode/geo", {"address": address})
        geocodes = cast(list[dict[str, object]], payload.get("geocodes", []))
        if not geocodes:
            raise ProviderResponseError("AMap geocode returned no coordinate")
        point = self._parse_location(geocodes[0].get("location"))
        if point is None:
            raise ProviderResponseError("AMap geocode coordinate is invalid")
        return point

    async def get_route(self, request: RouteRequest) -> RouteResult:
        endpoint = {
            "driving": "/v3/direction/driving",
            "walking": "/v3/direction/walking",
            "bicycling": "/v4/direction/bicycling",
            "transit": "/v3/direction/transit/integrated",
            "bus": "/v3/direction/transit/integrated",
            "subway": "/v3/direction/transit/integrated",
        }.get(request.mode)
        if endpoint is None:
            raise ProviderModeUnsupportedError(
                f"AMap does not provide {request.mode} route geometry"
            )
        params: dict[str, str | int | float | bool | None] = {
            "origin": self._format_point(request.origin),
            "destination": self._format_point(request.destination),
        }
        if request.mode in {"transit", "bus", "subway"}:
            if not request.city:
                raise ProviderResponseError("Transit routing requires city")
            params["city"] = request.city
            params["cityd"] = request.city
        if request.mode == "bicycling":
            payload = await self._request_v4(endpoint, params)
            data = cast(dict[str, object], payload.get("data", {}))
            paths = cast(list[dict[str, object]], data.get("paths", []))
            if not paths:
                raise ProviderResponseError("AMap bicycling route returned no path")
            selected = paths[0]
            polyline = self._steps_polyline(selected)
        else:
            payload = await self._request(endpoint, params)
            route = cast(dict[str, object], payload.get("route", {}))
            if request.mode in {"transit", "bus", "subway"}:
                transits = cast(list[dict[str, object]], route.get("transits", []))
                if not transits:
                    raise ProviderResponseError("AMap transit route returned no path")
                selected = self._select_transit(transits, request.mode)
                polyline = self._transit_polyline(selected)
            else:
                paths = cast(list[dict[str, object]], route.get("paths", []))
                if not paths:
                    raise ProviderResponseError("AMap route returned no path")
                selected = paths[0]
                polyline = self._steps_polyline(selected)

        return RouteResult(
            distance_m=int(float(str(selected.get("distance", 0)))),
            duration_s=int(float(str(selected.get("duration", 0)))),
            polyline=polyline,
            source=fresh_source(
                provider="amap",
                provider_place_id=None,
                source_url=None,
                freshness="live",
                confidence=0.95,
            ),
        )

    @staticmethod
    def _steps_polyline(route: dict[str, object]) -> str | None:
        steps = cast(list[dict[str, object]], route.get("steps", []))
        return ";".join(
            str(step["polyline"]) for step in steps if step.get("polyline")
        ) or None

    @classmethod
    def _transit_polyline(cls, transit: dict[str, object]) -> str | None:
        parts: list[str] = []
        segments = cast(list[dict[str, object]], transit.get("segments", []))
        for segment in segments:
            walking = segment.get("walking")
            if isinstance(walking, dict):
                walking_line = cls._steps_polyline(walking)
                if walking_line:
                    parts.append(walking_line)
            bus = segment.get("bus")
            if isinstance(bus, dict):
                buslines = cast(
                    list[dict[str, object]],
                    bus.get("buslines", []),
                )
                if buslines and buslines[0].get("polyline"):
                    parts.append(str(buslines[0]["polyline"]))
        return ";".join(parts) or None

    @classmethod
    def _select_transit(
        cls,
        transits: list[dict[str, object]],
        mode: str,
    ) -> dict[str, object]:
        if mode == "transit":
            return transits[0]
        for transit in transits:
            has_subway = cls._transit_has_subway(transit)
            has_bus = cls._transit_has_bus(transit)
            if mode == "subway" and has_subway:
                return transit
            if mode == "bus" and has_bus and not has_subway:
                return transit
        label = "地铁" if mode == "subway" else "公交"
        raise ProviderResponseError(f"AMap returned no {label}-only transit option")

    @classmethod
    def _transit_has_subway(cls, transit: dict[str, object]) -> bool:
        segments = cast(list[dict[str, object]], transit.get("segments", []))
        for segment in segments:
            bus = segment.get("bus")
            if not isinstance(bus, dict):
                continue
            buslines = cast(list[dict[str, object]], bus.get("buslines", []))
            for line in buslines:
                label = f"{line.get('name', '')} {line.get('type', '')}"
                if "地铁" in label or "轨道交通" in label:
                    return True
        return False

    @classmethod
    def _transit_has_bus(cls, transit: dict[str, object]) -> bool:
        segments = cast(list[dict[str, object]], transit.get("segments", []))
        for segment in segments:
            bus = segment.get("bus")
            if not isinstance(bus, dict):
                continue
            if cast(list[dict[str, object]], bus.get("buslines", [])):
                return True
        return False

    async def _request_v4(
        self,
        path: str,
        params: dict[str, str | int | float | bool | None],
    ) -> dict[str, object]:
        request_params = {**params, "key": self._key}
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.get(
                    f"{self._base_url}{path}",
                    params=request_params,
                    timeout=self._timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderTimeoutError("AMap v4 request timed out") from exc
            except httpx.HTTPError as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderUnavailableError("AMap v4 request failed") from exc

            if response.status_code == 429:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderRateLimitError("AMap v4 rate limit exceeded")
            if response.status_code >= 500:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderUnavailableError("AMap v4 service is unavailable")
            if response.status_code >= 400:
                raise ProviderUnavailableError(
                    f"AMap v4 returned HTTP {response.status_code}"
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise ProviderResponseError("AMap v4 returned invalid JSON") from exc
            if not isinstance(payload, dict):
                raise ProviderResponseError("AMap v4 response must be an object")
            if str(payload.get("errcode")) != "0":
                raise ProviderResponseError(
                    "AMap v4 rejected request "
                    f"(errcode={payload.get('errcode', 'unknown')}, "
                    f"errmsg={payload.get('errmsg', 'unknown')})"
                )
            return cast(dict[str, object], payload)
        raise ProviderUnavailableError("AMap v4 request failed")

    async def render_static_map(self, request: StaticMapRequest) -> StaticMapImage:
        markers = "|".join(
            f"mid,0x52634b,{marker.label[:1]}:{self._format_point(marker.point)}"
            for marker in request.markers
        )
        paths = "|".join(
            "8,0x52634b,0.9,,:"
            + ";".join(self._format_point(point) for point in path)
            for path in request.paths
            if len(path) >= 2
        )
        params: dict[str, str | int | float | bool | None] = {
            "location": self._format_point(request.center),
            "zoom": request.zoom,
            "size": f"{request.width}*{request.height}",
            "scale": 1,
        }
        if markers:
            params["markers"] = markers
        if paths:
            params["paths"] = paths
        content, content_type = await self._request_bytes("/v3/staticmap", params)
        return StaticMapImage(content=content, media_type=content_type)

    async def _request(
        self,
        path: str,
        params: dict[str, str | int | float | bool | None],
    ) -> dict[str, object]:
        request_params: dict[str, str | int | float | bool | None] = {
            **params,
            "key": self._key,
        }
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.get(
                    f"{self._base_url}{path}",
                    params=request_params,
                    timeout=self._timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderTimeoutError("AMap request timed out") from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderUnavailableError("AMap request failed") from exc

            if response.status_code == 429:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderRateLimitError("AMap rate limit exceeded")
            if response.status_code >= 500:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderUnavailableError("AMap service is unavailable")
            if response.status_code >= 400:
                raise ProviderUnavailableError(
                    f"AMap returned HTTP {response.status_code}"
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise ProviderResponseError("AMap returned invalid JSON") from exc
            if not isinstance(payload, dict):
                raise ProviderResponseError("AMap response must be an object")
            if str(payload.get("status")) != "1":
                infocode = str(payload.get("infocode", "unknown"))
                if infocode in _RATE_LIMIT_INFO_CODES:
                    raise ProviderRateLimitError("AMap quota or rate limit exceeded")
                raise ProviderResponseError(
                    f"AMap rejected request with infocode {infocode}"
                )
            return cast(dict[str, object], payload)

        raise ProviderUnavailableError("AMap request failed") from last_error

    async def _request_bytes(
        self,
        path: str,
        params: dict[str, str | int | float | bool | None],
    ) -> tuple[bytes, str]:
        request_params = {**params, "key": self._key}
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.get(
                    f"{self._base_url}{path}",
                    params=request_params,
                    timeout=self._timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderTimeoutError("AMap static map timed out") from exc
            except httpx.HTTPError as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderUnavailableError("AMap static map failed") from exc

            if response.status_code == 429:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderRateLimitError("AMap rate limit exceeded")
            if response.status_code >= 500:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_seconds * (2**attempt))
                    continue
                raise ProviderUnavailableError("AMap static map is unavailable")
            if response.status_code >= 400:
                raise ProviderUnavailableError(
                    f"AMap static map returned HTTP {response.status_code}"
                )
            content_type = response.headers.get("content-type", "")
            if content_type.startswith("image/"):
                return response.content, content_type.split(";")[0]
            raise ProviderResponseError("AMap static map did not return an image")
        raise ProviderUnavailableError("AMap static map failed")

    def _parse_place(self, poi: dict[str, object]) -> PlaceResult:
        provider_place_id = str(poi["id"])
        source_url = f"https://www.amap.com/place/{provider_place_id}"
        location = self._parse_location(poi.get("location"))
        address_parts = [
            str(poi.get(key))
            for key in ("pname", "cityname", "adname", "address")
            if poi.get(key) and str(poi.get(key)) not in {"[]"}
        ]
        biz_ext = poi.get("biz_ext")
        if isinstance(biz_ext, str):
            try:
                parsed_ext = json.loads(biz_ext)
                biz_ext = parsed_ext if isinstance(parsed_ext, dict) else {}
            except ValueError:
                biz_ext = {}
        if not isinstance(biz_ext, dict):
            biz_ext = {}
        opening_hours = [
            part.strip()
            for part in str(biz_ext.get("open_time") or "").split(";")
            if part.strip() and part.strip() not in {"[]", "unknown"}
        ]
        reference_price = str(biz_ext.get("cost") or "").strip() or None
        if reference_price in {"[]", "unknown"}:
            reference_price = None
        return PlaceResult(
            provider_place_id=provider_place_id,
            name=str(poi["name"]),
            category=self._normalize_category(poi.get("type")),
            address=" · ".join(dict.fromkeys(address_parts)) or None,
            location=location,
            tel=str(poi["tel"]) if poi.get("tel") and str(poi["tel"]) != "[]" else None,
            opening_hours=opening_hours,
            source=fresh_source(
                provider="amap",
                provider_place_id=provider_place_id,
                source_url=source_url,
                freshness="live",
                confidence=0.95 if location else 0.75,
                queried_at=datetime.now(UTC),
            ),
            reference_price=reference_price,
        )

    @staticmethod
    def _parse_location(value: object) -> GeoPoint | None:
        if not isinstance(value, str) or "," not in value:
            return None
        try:
            longitude_text, latitude_text = value.split(",", maxsplit=1)
            longitude = float(longitude_text)
            latitude = float(latitude_text)
        except ValueError:
            return None
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            return None
        return GeoPoint(longitude=longitude, latitude=latitude)

    @staticmethod
    def _format_point(point: GeoPoint) -> str:
        return f"{point.longitude:.6f},{point.latitude:.6f}"

    @staticmethod
    def _normalize_category(value: object) -> str | None:
        return normalize_category_text(value) if isinstance(value, str) else None
