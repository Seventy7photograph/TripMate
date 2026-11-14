# 文件说明：后端自动化测试：test_planning_events。
import httpx

from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


async def test_polling_returns_same_result_after_sse_disconnect(
    api_client: httpx.AsyncClient,
) -> None:
    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(destination="重庆"),
        )
    ).json()
    start = await api_client.post(
        f"/api/v1/trips/{trip['id']}/plan",
        headers=auth_headers(token),
        json={"expected_version": 1},
    )
    job_id = start.json()["job_id"]

    first = await api_client.get(
        f"/api/v1/jobs/{job_id}",
        headers=auth_headers(token),
    )
    second = await api_client.get(
        f"/api/v1/jobs/{job_id}",
        headers=auth_headers(token),
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["result"] == second.json()["result"]
    assert first.json()["events"] == second.json()["events"]
