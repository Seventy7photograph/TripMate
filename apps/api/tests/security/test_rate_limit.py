# 文件说明：后端自动化测试：test_rate_limit。
import httpx
import pytest

from app.api.deps import get_rate_limiter, get_settings
from app.core.config import Settings
from app.core.rate_limit import RateLimiter, RateLimitExceeded
from app.main import app
from tests.test_auth import auth_headers, register_user


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds

    async def ttl(self, key: str) -> int:
        return self.expirations.get(key, 60)


async def test_rate_limiter_blocks_after_limit_and_reports_retry() -> None:
    redis = FakeRedis()
    limiter = RateLimiter(redis)

    await limiter.check("upload:user-1", limit=2, window_seconds=60)
    await limiter.check("upload:user-1", limit=2, window_seconds=60)
    with pytest.raises(RateLimitExceeded) as raised:
        await limiter.check("upload:user-1", limit=2, window_seconds=60)

    assert raised.value.retry_after_seconds >= 1


async def test_sensitive_upload_endpoint_returns_429_and_retry_after(
    api_client: httpx.AsyncClient,
    tmp_path,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    redis = FakeRedis()
    settings = Settings(
        app_env="test",
        provider_profile="mock",
        map_provider_profile="mock",
        upload_dir=tmp_path,
        rate_limit_enabled=True,
        rate_limit_upload_per_minute=1,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(redis)
    try:
        first = await api_client.post(
            "/api/v1/uploads",
            headers=auth_headers(token),
            files={"file": ("one.txt", b"trip notes", "text/plain")},
        )
        second = await api_client.post(
            "/api/v1/uploads",
            headers=auth_headers(token),
            files={"file": ("two.txt", b"more notes", "text/plain")},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)
        app.dependency_overrides.pop(get_rate_limiter, None)

    assert first.status_code == 201
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "rate_limit_exceeded"
    assert int(second.headers["retry-after"]) >= 1
