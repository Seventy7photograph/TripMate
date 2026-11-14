# 文件说明：后端自动化测试：test_planning_worker。
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import httpx

from app.core.config import get_settings
from app.models.agent_run import AgentRun
from app.workers.planning_worker import requeue_unfinished_jobs
from tests.test_auth import auth_headers, register_user
from tests.test_trips_crud import trip_payload


class RecordingQueue:
    is_inline = False

    def __init__(self) -> None:
        self.job_ids: list[UUID] = []

    async def enqueue(self, job_id: UUID) -> None:
        self.job_ids.append(job_id)


async def test_requeue_only_includes_owned_planning_jobs(
    api_client: httpx.AsyncClient,
) -> None:
    from app.main import app

    registration = await register_user(api_client)
    token = str(registration["access_token"])
    trip = (
        await api_client.post(
            "/api/v1/trips",
            headers=auth_headers(token),
            json=trip_payload(),
        )
    ).json()
    session = app.state.test_session
    planning_job_id = uuid4()
    parsing_job_id = uuid4()
    session.add_all(
        [
            AgentRun(
                id=planning_job_id,
                trip_id=UUID(trip["id"]),
                created_by=UUID(str(registration["user"]["id"])),
                status="queued",
                progress=0,
                purpose="planning",
                provider="mock",
                model_name="mock",
                events=[],
            ),
            AgentRun(
                id=parsing_job_id,
                trip_id=None,
                created_by=UUID(str(registration["user"]["id"])),
                status="running",
                progress=10,
                purpose="requirement_parse",
                provider="mock",
                model_name="mock",
                events=[],
            ),
        ]
    )
    await session.flush()

    @asynccontextmanager
    async def session_factory() -> AsyncIterator[object]:
        yield session

    queue = RecordingQueue()
    count = await requeue_unfinished_jobs(
        get_settings(),
        queue=queue,  # type: ignore[arg-type]
        session_factory=session_factory,  # type: ignore[arg-type]
    )

    assert count == 1
    assert queue.job_ids == [planning_job_id]
    assert parsing_job_id not in queue.job_ids
