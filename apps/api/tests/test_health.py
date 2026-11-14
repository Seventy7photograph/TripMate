# 文件说明：后端自动化测试：test_health。
import httpx
import pytest

from app.api.v1.health import get_health_service
from app.main import app
from app.services.health import HealthReport


class StubHealthService:
    def __init__(self, report: HealthReport) -> None:
        self._report = report

    async def check(self) -> HealthReport:
        return self._report


@pytest.fixture
async def client() -> httpx.AsyncClient:
    app.dependency_overrides.clear()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


async def test_health_returns_ok_when_database_and_redis_are_healthy(
    client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_health_service] = lambda: StubHealthService(
        HealthReport(database="ok", redis="ok")
    )

    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "ok"}


async def test_health_returns_503_when_a_dependency_is_unhealthy(
    client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_health_service] = lambda: StubHealthService(
        HealthReport(database="error", redis="ok")
    )

    response = await client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "database": "error",
        "redis": "ok",
    }

