# 文件说明：MCP Gateway 固定 connector allowlist。

from urllib.parse import urlsplit

from app.core.config import Settings
from app.mcp.connectors.amap import amap_connector_definition
from app.mcp.connectors.weather import weather_connector_definition
from app.mcp.models import McpConnectorDefinition

_KNOWN_CONNECTORS = frozenset({"amap", "weather"})


class McpNotAllowedError(Exception):
    pass


class McpConnectorRegistry:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._allowed = frozenset(settings.mcp_allowed_connector_list)
        definitions: list[McpConnectorDefinition] = []
        amap_endpoint = _safe_endpoint(settings.mcp_amap_endpoint)
        if amap_endpoint is not None:
            definitions.append(
                amap_connector_definition(amap_endpoint)
            )
        weather_endpoint = _safe_endpoint(settings.mcp_weather_endpoint)
        if weather_endpoint is not None:
            definitions.append(
                weather_connector_definition(weather_endpoint)
            )
        self._definitions = {
            definition.connector_id: definition for definition in definitions
        }

    def resolve(self, connector_id: str) -> McpConnectorDefinition:
        normalized = connector_id.strip().lower()
        definition = self._definitions.get(normalized)
        if (
            not self._settings.mcp_gateway_enabled
            or normalized not in _KNOWN_CONNECTORS
            or normalized not in self._allowed
            or definition is None
        ):
            raise McpNotAllowedError(connector_id)
        return definition

    def resolve_url(self, url: str) -> McpConnectorDefinition:
        candidate = _canonical_endpoint(url)
        for definition in self._definitions.values():
            if (
                definition.endpoint == candidate
                and definition.connector_id in self._allowed
                and self._settings.mcp_gateway_enabled
            ):
                return definition
        raise McpNotAllowedError(url)

    @property
    def configured_connectors(self) -> frozenset[str]:
        return frozenset(
            connector_id
            for connector_id in self._definitions
            if connector_id in self._allowed
        )

    @property
    def known_connectors(self) -> frozenset[str]:
        return _KNOWN_CONNECTORS


def _safe_endpoint(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return _canonical_endpoint(value)


def _canonical_endpoint(value: str) -> str:
    normalized = value.strip()
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise McpNotAllowedError(value)
    if parsed.username is not None or parsed.password is not None:
        raise McpNotAllowedError(value)
    if parsed.query or parsed.fragment:
        raise McpNotAllowedError(value)
    if parsed.scheme == "http" and parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise McpNotAllowedError(value)
    return normalized.rstrip("/")
