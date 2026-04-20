from fastapi import FastAPI
from app.api.basketball import router as basketball_router

app = FastAPI(
    title="Basketball Projection API",
    version="1.0.0"
)

app.include_router(basketball_router, prefix="/api")

@app.get("/health")
def health_check():
    return {"status": "ok"}