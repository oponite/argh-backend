from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services.basketball.api import router as basketball_router
from app.services.system.api import router as system_router
from app.core.config import settings

from app.core.deps.http_client import ClientManager
from app.services.background.scheduler import scheduler
import asyncio

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    asyncio.create_task(scheduler())
    yield
    # Shutdown
    await ClientManager.close_client()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

if settings.cors_allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(basketball_router, prefix="/api")
app.include_router(system_router, prefix="/api")

@app.get("/health")
def health_check():
    return {"status": "ok"}
