# 文件说明：后端自动化测试：test_partial_replan。
from uuid import uuid4

import httpx

from tests.test_auth import auth_headers
from tests.test_patch_apply import create_patch_fixture


async def test_partial_replan_rejects_unknown_day(
    api_client: httpx.AsyncClient,
) -> None:
    fixture = await create_patch_fixture(api_client)
    response = await api_client.post(
        f"/api/v1/trips/{fixture.trip_id}/replan",
        headers=auth_headers(fixture.token),
        json={
            "expected_version": fixture.version,
            "day_id": str(uuid4()),
            "instruction": "减少一个景点",
        },
    )
    assert response.status_code == 404


async def test_partial_replan_rejects_unsupported_instruction(
    api_client: httpx.AsyncClient,
) -> None:
    fixture = await create_patch_fixture(api_client)
    response = await api_client.post(
        f"/api/v1/trips/{fixture.trip_id}/replan",
        headers=auth_headers(fixture.token),
        json={
            "expected_version": fixture.version,
            "day_id": fixture.first_day_id,
            "instruction": "换一个完全不同的城市",
        },
    )
    assert response.status_code == 422
