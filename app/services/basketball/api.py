from app.services.basketball.schemas import ProjectionRequest, ProjectionResponse
from app.services.basketball.logic import build_projection
from app.core.errors import StatsServiceError
from app.core.deps.http_client import get_http_client
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
