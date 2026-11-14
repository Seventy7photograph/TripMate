# 文件说明：后端自动化测试：conftest。
import os
from collections.abc import AsyncIterator
from uuid import uuid4

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("PROVIDER_PROFILE", "mock")
os.environ.setdefault("MAP_PROVIDER_PROFILE", "mock")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import httpx
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models import (  # noqa: F401
    AdminAuditLogModel,
    AgentModelConfigModel,
    AgentRunModel,
    ExpenseModel,
    FeatureFlagModel,
    ItineraryStopModel,
    McpConnectorStateModel,
    PlaceModel,
    PlaceSearchCacheModel,
    ProviderHealthModel,
    RouteLegModel,
    ToolCallLogModel,
    TripDayModel,
    TripModel,
    TripVersionModel,
    UploadedAssetModel,
    UserMemoryModel,
    UserModel,
)


@pytest_asyncio.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    settings = get_settings()
    schema = f"test_{uuid4().hex}"
    admin_engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    test_engine = create_async_engine(
        settings.database_url,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )
    async with test_engine.begin() as connection:
        # The schema is new; skip catalog checkfirst so public tables are not
        # mistaken for tables that already exist in the isolated test schema.
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                checkfirst=False,
            )
        )

    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    app.state.test_session = session

    async def override_db_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db_session] = override_db_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    del app.state.test_session
    await session.close()
    await transaction.rollback()
    await connection.close()
    async with admin_engine.connect() as admin_connection:
        await admin_connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    await test_engine.dispose()
    await admin_engine.dispose()
