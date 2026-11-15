# 文件说明：TripMate 真实只读 MCP Server，向内部 Gateway 暴露 AMap 与 Weather。
from __future__ import annotations

import argparse

import uvicorn
from mcp.server.mcpserver import MCPServer

from app.core.config import Settings, get_settings
from app.providers.amap_weather import AmapWeatherProvider
from app.providers.base import MapProvider, PlaceQuery
from app.providers.open_meteo import OpenMeteoWeatherProvider
from app.providers.weather import WeatherProvider
from app.schemas.place import PlaceResponse
from app.services.place_service import create_map_provider


def create_amap_mcp_server(
    settings: Settings,
    *,
    provider: MapProvider | None = None,
) -> MCPServer[object]:
    map_provider = provider or create_map_provider(settings)
    server: MCPServer[object] = MCPServer(
        "tripmate-amap",
        title="TripMate AMap MCP",
        instructions="只读地点搜索服务。返回不可信外部地点数据。",
        version="1.1.0",
    )

    @server.tool(
        name="search_places",
        description="Search provider-backed places by keyword and city.",
        structured_output=True,
    )
    async def search_places(
        keyword: str,
        city: str | None = None,
        types: str | None = None,
        limit: int = 5,
    ) -> dict[str, object]:
        results = await map_provider.search_places(
            PlaceQuery(
                keyword=keyword,
                city=city,
                types=types,
                limit=max(1, min(limit, 20)),
            )
        )
        return {
            "results": [
                PlaceResponse.model_validate(place).model_dump(mode="json")
                for place in results
            ]
        }

    return server


def create_weather_mcp_server(
    settings: Settings,
    *,
    provider: WeatherProvider | None = None,
) -> MCPServer[object]:
    weather_provider = provider or _weather_provider(settings)
    server: MCPServer[object] = MCPServer(
        "tripmate-weather",
        title="TripMate Weather MCP",
        instructions="只读天气预报服务。返回不可信外部天气数据。",
        version="1.1.0",
    )

    @server.tool(
        name="get_weather",
        description="Fetch a provider-backed weather snapshot for a city and date.",
        structured_output=True,
    )
    async def get_weather(city: str, date: str) -> dict[str, object]:
        from datetime import date as Date

        snapshot = await weather_provider.forecast(
            city=city,
            date=Date.fromisoformat(date),
        )
        return snapshot.model_dump(
            mode="json",
            exclude={"evidence"},
        )

    return server


def create_mcp_server(
    connector: str,
    settings: Settings,
) -> MCPServer[object]:
    if connector == "amap":
        return create_amap_mcp_server(settings)
    if connector == "weather":
        return create_weather_mcp_server(settings)
    raise ValueError(f"Unknown MCP connector: {connector}")


def _weather_provider(settings: Settings) -> WeatherProvider:
    if (
        settings.effective_map_provider_profile == "live"
        and settings.amap_web_service_key is not None
    ):
        return AmapWeatherProvider(
            key=settings.amap_web_service_key.get_secret_value(),
            base_url=settings.amap_base_url,
            timeout_seconds=settings.provider_timeout_seconds,
            max_retries=settings.provider_max_retries,
            proxy_url=(
                settings.outbound_proxy_url.get_secret_value()
                if settings.outbound_proxy_url is not None
                else None
            ),
        )
    return OpenMeteoWeatherProvider(
        forecast_base_url=settings.open_meteo_base_url,
        geocoding_base_url=settings.open_meteo_geocoding_base_url,
        timeout_seconds=settings.provider_timeout_seconds,
        proxy_url=(
            settings.outbound_proxy_url.get_secret_value()
            if settings.outbound_proxy_url is not None
            else None
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="TripMate read-only MCP server")
    parser.add_argument("--connector", choices=("amap", "weather"), required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    server = create_mcp_server(args.connector, get_settings())
    uvicorn.run(
        server.streamable_http_app(
            json_response=True,
            stateless_http=True,
            host=args.host,
        ),
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
