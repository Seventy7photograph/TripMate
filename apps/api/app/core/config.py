# 文件说明：核心基础设施：config。
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    provider_profile: Literal["mock", "live"] = "live"
    map_provider_profile: Literal["mock", "live"] | None = None
    amap_web_service_key: SecretStr | None = None
    amap_base_url: str = "https://restapi.amap.com"
    open_meteo_base_url: str = "https://api.open-meteo.com"
    open_meteo_geocoding_base_url: str = "https://geocoding-api.open-meteo.com"
    open_meteo_elevation_base_url: str = "https://api.open-meteo.com"
    weather_fallback_enabled: bool = True
    mcp_gateway_enabled: bool = False
    mcp_allowed_connectors: str = ""
    mcp_amap_endpoint: str | None = None
    mcp_weather_endpoint: str | None = None
    mcp_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    mcp_rate_limit_per_minute: int = Field(default=60, ge=1, le=600)
    mcp_daily_quota_per_connector: int = Field(default=1_000, ge=1)
    provider_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    provider_max_retries: int = Field(default=2, ge=0, le=5)
    place_cache_ttl_seconds: int = Field(default=900, ge=0, le=86_400)
    route_cache_ttl_seconds: int = Field(default=900, ge=0, le=86_400)
    llm_api_key: SecretStr | None = None
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-flash"
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_max_repairs: int = Field(default=2, ge=0, le=2)
    model_config_db_enabled: bool = True
    model_config_encryption_key: SecretStr | None = None
    planning_timeout_seconds: float = Field(default=120.0, gt=0, le=600)
    planning_max_tool_calls: int = Field(default=12, ge=1, le=12)
    planning_max_loops: int = Field(default=2, ge=0, le=2)
    planning_max_cost_minor: int = Field(default=1_000, ge=0)
    travel_chat_max_cost_minor: int = Field(default=1_000, ge=1)
    brief_parse_max_cost_minor: int = Field(default=500, ge=1)
    skills_root: Path = PROJECT_ROOT / "skills"
    prompts_root: Path = PROJECT_ROOT / "apps" / "api" / "prompts"
    daily_user_cost_limit_minor: int = Field(default=10_000, ge=1)
    daily_ip_cost_limit_minor: int = Field(default=30_000, ge=1)
    daily_provider_cost_limit_minor: int = Field(default=200_000, ge=1)
    cost_warning_ratio: float = Field(default=0.8, gt=0, le=1)
    upload_dir: Path = PROJECT_ROOT / "output" / "uploads"
    max_image_upload_bytes: int = Field(default=5 * 1024 * 1024, ge=1)
    max_document_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    max_uploads_per_message: int = Field(default=3, ge=1, le=6)
    max_extracted_text_chars: int = Field(default=50_000, ge=1_000, le=200_000)
    max_image_pixels: int = Field(default=20_000_000, ge=1_000)
    max_image_dimension: int = Field(default=1_600, ge=256, le=4_096)
    upload_ttl_hours: int = Field(default=24, ge=1, le=720)
    clamav_host: str | None = None
    clamav_port: int = Field(default=3_310, ge=1, le=65_535)
    clamav_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    outbound_proxy_url: SecretStr | None = None
    rate_limit_enabled: bool = True
    rate_limit_upload_per_minute: int = Field(default=6, ge=1, le=120)
    rate_limit_brief_parse_per_minute: int = Field(default=12, ge=1, le=240)
    rate_limit_planning_per_minute: int = Field(default=6, ge=1, le=120)
    rate_limit_travel_chat_per_minute: int = Field(default=12, ge=1, le=240)
    security_headers_enabled: bool = True
    allow_private_provider_urls: bool = False
    provider_allowed_hosts: str = ""
    planning_queue_key: str = "tripmate:planning:jobs"
    planning_worker_enabled: bool = True
    database_url: str = "postgresql+asyncpg://tripmate:tripmate@localhost:5432/tripmate"
    redis_url: str = "redis://localhost:6379/0"
    health_check_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    cors_origins: str = "http://localhost:5173,http://localhost:5174"
    jwt_secret: SecretStr = SecretStr("tripmate-development-only-change-before-production")
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "tripmate"
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def provider_allowed_host_list(self) -> list[str]:
        return [
            host.strip().lower()
            for host in self.provider_allowed_hosts.split(",")
            if host.strip()
        ]

    @property
    def mcp_allowed_connector_list(self) -> list[str]:
        return [
            connector.strip().lower()
            for connector in self.mcp_allowed_connectors.split(",")
            if connector.strip()
        ]

    @property
    def effective_map_provider_profile(self) -> Literal["mock", "live"]:
        return self.map_provider_profile or self.provider_profile

    @property
    def postgres_checkpoint_url(self) -> str:
        return self.database_url.replace(
            "postgresql+asyncpg://",
            "postgresql://",
            1,
        )

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        secret = self.jwt_secret.get_secret_value()
        insecure_values = {
            "tripmate-development-only-change-before-production",
            "replace-with-at-least-32-random-characters",
        }
        if self.app_env == "production" and (len(secret) < 32 or secret in insecure_values):
            raise ValueError("JWT_SECRET must be a random value of at least 32 characters")
        if self.app_env == "production" and self.provider_profile != "live":
            raise ValueError("PROVIDER_PROFILE must be live in production")
        if self.app_env == "production" and self.effective_map_provider_profile != "live":
            raise ValueError("MAP_PROVIDER_PROFILE must be live in production")
        if self.app_env == "production":
            encryption_key = (
                None
                if self.model_config_encryption_key is None
                else self.model_config_encryption_key.get_secret_value()
            )
            if encryption_key is None or len(encryption_key) < 32:
                raise ValueError(
                    "MODEL_CONFIG_ENCRYPTION_KEY must be at least 32 characters "
                    "in production"
                )
            if encryption_key == secret:
                raise ValueError(
                    "MODEL_CONFIG_ENCRYPTION_KEY must differ from JWT_SECRET"
                )
            if self.clamav_host is None or not self.clamav_host.strip():
                raise ValueError("CLAMAV_HOST is required in production")
            proxy_url = (
                None
                if self.outbound_proxy_url is None
                else self.outbound_proxy_url.get_secret_value()
            )
            parsed_proxy = (
                None if proxy_url is None else urlparse(proxy_url.strip())
            )
            if (
                parsed_proxy is None
                or parsed_proxy.scheme not in {"http", "https"}
                or not parsed_proxy.hostname
                or parsed_proxy.username is not None
                or parsed_proxy.password is not None
            ):
                raise ValueError(
                    "OUTBOUND_PROXY_URL must be an HTTP(S) proxy URL "
                    "without credentials in production"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
