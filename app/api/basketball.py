from app.models.requests import ProjectionRequest
from app.models.responses import ProjectionResponse
from app.services.projection import build_projection
from app.errors import StatsServiceError
from app.api.deps.http_client import get_http_client
import httpx
from fastapi import APIRouter, HTTPException, Depends

router = APIRouter()

@router.post("/basketball/projection", response_model=ProjectionResponse, tags=["basketball"])
async def basketball_projection(
    request: ProjectionRequest,
    client: httpx.AsyncClient = Depends(get_http_client)
):
    try:
        return await build_projection(
            client=client,
            away_team=request.away_team,
            home_team=request.home_team,
        )
    except StatsServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
