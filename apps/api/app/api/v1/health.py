# 文件说明：FastAPI 路由：health。
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.health import HealthChecker, InfrastructureHealthService

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]
    redis: Literal["ok", "error"]


def get_health_service() -> HealthChecker:
    return InfrastructureHealthService(get_settings())


HealthServiceDep = Annotated[HealthChecker, Depends(get_health_service)]


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def health(response: Response, service: HealthServiceDep) -> HealthResponse:
    report = await service.check()
    healthy = report.healthy
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if healthy else "degraded",
        database=report.database,
        redis=report.redis,
    )

