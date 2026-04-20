from pydantic import BaseModel

class ProjectionRequest(BaseModel):
    away_team: str
    home_team: str
    bookie_total: float