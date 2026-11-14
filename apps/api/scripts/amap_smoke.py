# 文件说明：高德 Provider 契约冒烟脚本。
import asyncio
import json

from app.core.config import get_settings
from app.providers.amap import AmapMapProvider
from app.providers.base import PlaceQuery, RouteRequest


async def main() -> None:
    settings = get_settings()
    if settings.amap_web_service_key is None:
        raise SystemExit("AMAP_WEB_SERVICE_KEY is not configured")

    provider = AmapMapProvider(
        key=settings.amap_web_service_key.get_secret_value(),
        base_url=settings.amap_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        max_retries=settings.provider_max_retries,
    )
    try:
        results = await provider.search_places(
            PlaceQuery(keyword="洪崖洞", city="重庆", limit=2)
        )
        detail = await provider.get_place(results[0].provider_place_id)
        point = await provider.geocode("重庆市渝中区洪崖洞")
        route = None
        if len(results) > 1 and results[0].location and results[1].location:
            route = await provider.get_route(
                RouteRequest(
                    origin=results[0].location,
                    destination=results[1].location,
                    mode="driving",
                )
            )
    finally:
        await provider.close()

    print(
        json.dumps(
            {
                "count": len(results),
                "provider": results[0].source.provider,
                "freshness": results[0].source.freshness,
                "detail_has_address": bool(detail.address),
                "geocode_coordinate_system": point.coordinate_system,
                "route_distance_m": route.distance_m if route else None,
                "route_duration_s": route.duration_s if route else None,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
