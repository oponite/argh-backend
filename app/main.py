from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.basketball import router as basketball_router
from app.api.system import router as system_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
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
