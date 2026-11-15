# 文件说明：后端自动化测试：Provider Health 真实写入与 Upsert。
import httpx
from sqlalchemy import select

from app.main import app
from app.models.provider_health import ProviderHealth
from app.services.provider_health_service import ProviderHealthService
from app.tools.base import ToolCallAudit


async def test_provider_health_service_persists_and_updates_audits(
    api_client: httpx.AsyncClient,
) -> None:
    del api_client
    service = ProviderHealthService(app.state.test_session)

    await service.record_audit(
        ToolCallAudit(
            tool_name="search_places",
            provider="mcp:amap",
            input_hash="a" * 64,
            status="success",
            latency_ms=120,
            estimated_cost_minor=0,
        )
    )
    await service.record_audit(
        ToolCallAudit(
            tool_name="search_places",
            provider="mcp:amap",
            input_hash="b" * 64,
            status="error",
            latency_ms=240,
            estimated_cost_minor=0,
            error_code="mcp_transport_error",
        )
    )
    await app.state.test_session.commit()

    rows = list(
        (
            await app.state.test_session.execute(
                select(ProviderHealth)
            )
        ).scalars()
    )
    assert len(rows) == 1
    assert rows[0].provider_key == "map_provider"
    assert rows[0].provider_type == "map"
    assert rows[0].provider_name == "mcp:amap"
    assert rows[0].status == "degraded"
    assert rows[0].latency_ms == 240
    assert rows[0].error_code == "mcp_transport_error"
