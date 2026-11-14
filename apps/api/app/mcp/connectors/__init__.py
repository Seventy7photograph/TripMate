# 文件说明：MCP 固定 connector 集合。

from app.mcp.connectors.amap import amap_connector_definition
from app.mcp.connectors.weather import weather_connector_definition

__all__ = [
    "amap_connector_definition",
    "weather_connector_definition",
]
