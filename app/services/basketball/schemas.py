from pydantic import BaseModel, Field

class ProjectionRequest(BaseModel):
    away_team: str = Field(min_length=2, max_length=64)
    home_team: str = Field(min_length=2, max_length=64)


class TeamMetricsResponse(BaseModel):
    off_rating: float | None
    def_rating: float | None
    pace: float | None
    three_point_pct: float | None
    three_point_pct_text: str | None


class LeagueMetricsResponse(BaseModel):
    avg_3pt_pct: float
    std_dev_3pt_pct: float


class ProjectionResponse(BaseModel):
    away_team_name: str
    home_team_name: str

    projected_total: float
    projected_total_std_dev: float

    away: TeamMetricsResponse
    home: TeamMetricsResponse
    league: LeagueMetricsResponse
