# 文件说明：后端自动化测试：test_health_critical。
import httpx

from app.api.v1.health import get_health_service
from app.main import app
from app.services.health import HealthReport


class UnhealthyService:
    async def check(self) -> HealthReport:
        return HealthReport(database="ok", redis="error")


async def test_health_fails_closed_when_redis_is_down() -> None:
    app.dependency_overrides[get_health_service] = lambda: UnhealthyService()
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
