# 文件说明：后端应用模块：main。
import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import auth_router, users_router
from app.api.v1.briefs import router as briefs_router
from app.api.v1.budgets import router as budget_router
from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.favorites import router as favorites_router
from app.api.v1.health import router as health_router
from app.api.v1.itinerary import router as itinerary_router
from app.api.v1.memories import router as memories_router
from app.api.v1.patches import router as patches_router
from app.api.v1.places import router as places_router
from app.api.v1.planning import router as planning_router
from app.api.v1.routes import router as routes_router
from app.api.v1.shares import router as shares_router
from app.api.v1.trips import router as trips_router
from app.api.v1.uploads import router as uploads_router
from app.core.config import get_settings
from app.core.rate_limit import get_redis_client
from app.core.security_headers import install_security_headers
from app.db.session import engine

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    worker_task: asyncio.Task[None] | None = None
    if settings.planning_worker_enabled:
        from app.workers.planning_worker import planning_worker_loop

        worker_ready = asyncio.Event()
        worker_task = asyncio.create_task(
            planning_worker_loop(settings, worker_ready),
            name="tripmate-planning-worker",
        )
        await asyncio.wait_for(worker_ready.wait(), timeout=30)
    yield
    if worker_task is not None:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task
    await get_redis_client(settings.redis_url).aclose()
    await engine.dispose()


app = FastAPI(title="TripMate API", version="1.0.0", lifespan=lifespan)
install_security_headers(app, settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(briefs_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(favorites_router, prefix="/api/v1")
app.include_router(memories_router, prefix="/api/v1")
app.include_router(trips_router, prefix="/api/v1")
app.include_router(itinerary_router, prefix="/api/v1")
app.include_router(places_router, prefix="/api/v1")
app.include_router(routes_router, prefix="/api/v1")
app.include_router(budget_router, prefix="/api/v1")
app.include_router(planning_router, prefix="/api/v1")
app.include_router(patches_router, prefix="/api/v1")
app.include_router(shares_router, prefix="/api/v1")
app.include_router(uploads_router, prefix="/api/v1")
