from pydantic import BaseModel, Field

class ProjectionRequest(BaseModel):
    away_team: str = Field(min_length=2, max_length=64)
    home_team: str = Field(min_length=2, max_length=64)
