# 文件说明：AMap MCP connector 包装。

from app.mcp.models import McpConnectorDefinition, McpToolBinding
from app.providers.base import MapProvider
from app.tools.context import ToolContext
from app.tools.place_tools import PlaceTool


class AmapConnector:
    connector_id = "amap"

    @staticmethod
    def local_tool(provider: MapProvider, context: ToolContext) -> PlaceTool:
        # MCP fallback 与主链路复用同一个 Provider Adapter 和 Tool Schema。
        return PlaceTool(provider, context)


def amap_connector_definition(endpoint: str) -> McpConnectorDefinition:
    spec = PlaceTool.spec()
    if spec.provider_type != "map":
        raise ValueError("AMap connector requires the map provider type")
    return McpConnectorDefinition(
        connector_id=AmapConnector.connector_id,
        provider_type="map",
        endpoint=endpoint,
        tools=(
            McpToolBinding(
                name=spec.name,
                provider_type="map",
                output_kind="place_search",
            ),
        ),
    )
