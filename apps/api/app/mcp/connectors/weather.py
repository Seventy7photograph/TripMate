# 文件说明：Weather MCP connector 包装。

from app.core.config import Settings
from app.mcp.models import McpConnectorDefinition, McpToolBinding
from app.tools.context import ToolContext
from app.tools.weather_tools import WeatherTool, create_weather_tool


class WeatherConnector:
    connector_id = "weather"

    @staticmethod
    def local_tool(settings: Settings, context: ToolContext) -> WeatherTool:
        # fallback 复用现有 AMap/Open-Meteo Provider 组合与 Evidence 写入。
        return create_weather_tool(settings, context)


def weather_connector_definition(endpoint: str) -> McpConnectorDefinition:
    spec = WeatherTool.spec()
    if spec.provider_type != "weather":
        raise ValueError("Weather connector requires the weather provider type")
    return McpConnectorDefinition(
        connector_id=WeatherConnector.connector_id,
        provider_type="weather",
        endpoint=endpoint,
        tools=(
            McpToolBinding(
                name=spec.name,
                provider_type="weather",
            ),
        ),
    )
