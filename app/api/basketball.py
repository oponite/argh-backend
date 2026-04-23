from fastapi import APIRouter, HTTPException
from app.models.requests import ProjectionRequest
from app.models.responses import ProjectionResponse
from app.services.projection import build_projection
from app.errors import StatsServiceError

router = APIRouter()

@router.post("/basketball/projection", response_model=ProjectionResponse, tags=["basketball"])
async def basketball_projection(request: ProjectionRequest):
    try:
        return await build_projection(
            away_team=request.away_team,
            home_team=request.home_team,
            bookie_total=request.bookie_total,
        )
    except StatsServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
