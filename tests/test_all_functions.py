import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main
from app.services.basketball import api as basketball
from app.services.system import api as system
from app.core.deps.auth import require_auth
from app.core.errors import InvalidResponseError, RequestFailedError, StatsServiceError, TeamNotFoundError
from app.services.basketball.schemas import (
    LeagueMetricsResponse,
    ProjectionRequest,
    ProjectionResponse,
    TeamMetricsResponse,
)
from app.services.basketball.integrations import nba_stats
from app.services.basketball import logic as projection
from app.services.basketball.integrations.nba_stats import GameAdvancedMetrics, TeamMetrics
from app.core.utils.normalization import normalize
from app.core.utils.statistics import mean, std_dev


def trace(function_name, inputs, output):
    print(f"[TRACE] {function_name}")
    print(f"  input: {inputs}")
    print(f"  output: {output}")
    return output


def run(coro, function_name=None, inputs=None):
    output = asyncio.run(coro)
    if function_name:
        trace(function_name, inputs, output)
    return output


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self, responses):
        self._responses = list(responses)

    async def get(self, url, params, **kwargs):
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _team_metrics(name):
    games = [
        GameAdvancedMetrics(off_rating=110.0, def_rating=108.0, pace=99.0),
        GameAdvancedMetrics(off_rating=112.0, def_rating=106.0, pace=101.0),
    ]
    return TeamMetrics(
        display_name=name,
        recent_games=games,
        off_rating_mean=111.0,
        def_rating_mean=107.0,
        pace_mean=100.0,
        three_point_pct=36.4,
        three_point_pct_text="36.4",
        league_average_three_point_pct=35.8,
        league_three_point_pct_standard_deviation=2.1,
    )


def test_health_check():
    out = main.health_check()
    trace("health_check", {}, out)
    assert out == {"status": "ok"}


def test_normalize():
    inp = "  LA-Lakers!!  "
    out = normalize(inp)
    trace("normalize", {"value": inp}, out)
    assert out == "la lakers"


def test_statistics_helpers():
    out_mean_123 = mean([1, 2, 3])
    trace("mean", {"values": [1, 2, 3]}, out_mean_123)
    assert out_mean_123 == 2.0

    out_mean_empty = mean([])
    trace("mean", {"values": []}, out_mean_empty)
    assert out_mean_empty == 0.0

    out_std = std_dev([2, 2, 2])
    trace("std_dev", {"values": [2, 2, 2]}, out_std)
    assert out_std == 1e-6


def test_response_models_construct():
    away = TeamMetricsResponse(
        off_rating=111.0,
        def_rating=107.0,
        pace=100.0,
        three_point_pct=36.4,
        three_point_pct_text="36.4",
    )
    home = TeamMetricsResponse(
        off_rating=109.0,
        def_rating=108.0,
        pace=99.0,
        three_point_pct=35.2,
        three_point_pct_text="35.2",
    )
    league = LeagueMetricsResponse(avg_3pt_pct=35.8, std_dev_3pt_pct=2.1)
    payload = ProjectionResponse(
        away_team_name="Boston Celtics",
        home_team_name="New York Knicks",
        projected_total=221.5,
        projected_total_std_dev=6.8,
        away=away,
        home=home,
        league=league,
    )
    trace(
        "ProjectionResponse",
        {
            "away_team_name": "Boston Celtics",
            "home_team_name": "New York Knicks",
            "projected_total": 221.5,
            "projected_total_std_dev": 6.8,
            "away": away.model_dump(),
            "home": home.model_dump(),
            "league": league.model_dump(),
        },
        payload.model_dump(),
    )
    assert payload.away_team_name == "Boston Celtics"
    assert payload.league.avg_3pt_pct == 35.8


def test_nba_stat_helpers_and_models():
    row = {"TEAM_NAME": "Boston Celtics", "TEAM_ID": "1610612738", "X": "4.2", "Y": 5}

    out_matches_team = nba_stats.matches_team(row, "boston celtics")
    trace("matches_team", {"row": row, "expected_name": "boston celtics"}, out_matches_team)
    assert out_matches_team is True

    out_match_team_id = nba_stats.row_matches_team_id(row, 1610612738)
    trace("row_matches_team_id", {"row": row, "team_id": 1610612738}, out_match_team_id)
    assert out_match_team_id is True

    out_no_match_id = nba_stats.row_matches_team_id({"TEAM_ID": "nope"}, 1)
    trace("row_matches_team_id", {"row": {"TEAM_ID": "nope"}, "team_id": 1}, out_no_match_id)
    assert out_no_match_id is False

    out_value_x = nba_stats.value_for(["X"], row)
    trace("value_for", {"keys": ["X"], "row": row}, out_value_x)
    assert out_value_x == 4.2

    out_value_y = nba_stats.value_for(["Y"], row)
    trace("value_for", {"keys": ["Y"], "row": row}, out_value_y)
    assert out_value_y == 5.0

    out_value_z = nba_stats.value_for(["Z"], row)
    trace("value_for", {"keys": ["Z"], "row": row}, out_value_z)
    assert out_value_z is None

    out_pct_34 = nba_stats.format_percentage_text(34.0)
    trace("format_percentage_text", {"value": 34.0}, out_pct_34)
    assert out_pct_34 == "34"

    out_pct_345 = nba_stats.format_percentage_text(34.5)
    trace("format_percentage_text", {"value": 34.5}, out_pct_345)
    assert out_pct_345 == "34.5"

    season = nba_stats.current_season_string()
    trace("current_season_string", {}, season)
    year = datetime.now(UTC).year
    assert season.startswith(str(year - 1)) or season.startswith(str(year))

    params = nba_stats.query_items(measure_type="Advanced", last_n_games=5)
    trace("query_items", {"measure_type": "Advanced", "last_n_games": 5}, params)
    assert params["MeasureType"] == "Advanced"
    assert params["LastNGames"] == "5"

    tm = _team_metrics("Boston Celtics")
    as_dict = tm.as_dict()
    league_metrics = tm.league_metrics()
    trace("TeamMetrics.as_dict", {"display_name": tm.display_name}, as_dict)
    trace("TeamMetrics.league_metrics", {"display_name": tm.display_name}, league_metrics)
    assert as_dict["off_rating"] == 111.0
    assert league_metrics["avg_3pt_pct"] == 35.8


def test_fetch_result_set_rows_success():
    payload = {
        "resultSets": [
            {
                "name": "LeagueDashTeamStats",
                "headers": ["TEAM_NAME", "PCT_PTS_3PT"],
                "rowSet": [["Boston Celtics", 0.37]],
            }
        ]
    }
    client = DummyClient([DummyResponse(payload)])
    rows = run(
        nba_stats.fetch_result_set_rows(client, "http://x", {}, None),
        function_name="fetch_result_set_rows",
        inputs={"url": "http://x", "params": {}, "preferred_result_set_name": None},
    )
    assert rows == [{"TEAM_NAME": "Boston Celtics", "PCT_PTS_3PT": 0.37}]


def test_fetch_result_set_rows_with_preferred_set_name():
    payload = {
        "resultSets": [
            {
                "name": "Other",
                "headers": ["A"],
                "rowSet": [[1]],
            },
            {
                "name": "TeamStats",
                "headers": ["TEAM_ID", "OFF_RATING", "DEF_RATING", "PACE"],
                "rowSet": [[1610612738, 110.0, 108.0, 99.0]],
            },
        ]
    }
    client = DummyClient([DummyResponse(payload)])
    rows = run(
        nba_stats.fetch_result_set_rows(client, "http://x", {}, preferred_result_set_name="TeamStats"),
        function_name="fetch_result_set_rows",
        inputs={"url": "http://x", "params": {}, "preferred_result_set_name": "TeamStats"},
    )
    assert rows[0]["TEAM_ID"] == 1610612738


def test_fetch_result_set_rows_retries_then_raises(monkeypatch):
    async def no_sleep(_x):
        return None

    monkeypatch.setattr(nba_stats.asyncio, "sleep", no_sleep)
    client = DummyClient([RuntimeError("boom"), RuntimeError("boom2"), RuntimeError("boom3")])

    with pytest.raises(RequestFailedError) as exc:
        run(nba_stats.fetch_result_set_rows(client, "http://x", {}, None))
    trace(
        "fetch_result_set_rows",
        {"url": "http://x", "params": {}, "preferred_result_set_name": None},
        f"raised {type(exc.value).__name__}",
    )


def test_fetch_rows_delegates(monkeypatch):
    async def fake_fetch_result_set_rows(client, url, params, preferred_result_set_name=None):
        assert "leaguedashteamstats" in url
        assert params["MeasureType"] == "Advanced"
        assert params["LastNGames"] == "5"
        return [{"TEAM_NAME": "Boston Celtics"}]

    monkeypatch.setattr(nba_stats, "fetch_result_set_rows", fake_fetch_result_set_rows)
    rows = run(
        nba_stats.fetch_rows(client=object(), measure_type="Advanced", last_n_games=5),
        function_name="fetch_rows",
        inputs={"measure_type": "Advanced", "last_n_games": 5},
    )
    assert rows == [{"TEAM_NAME": "Boston Celtics"}]


def test_fetch_recent_game_ids_success(monkeypatch):
    async def fake_fetch_result_set_rows(client, url, params, preferred_result_set_name=None):
        return [
            {"Game_ID": "1"},
            {"Game_ID": 2},
            {"Game_ID": 3.0},
            {"Game_ID": "4"},
            {"Game_ID": 5},
        ]

    monkeypatch.setattr(nba_stats, "fetch_result_set_rows", fake_fetch_result_set_rows)
    out = run(
        nba_stats.fetch_recent_game_ids(client=object(), team_id=1610612738),
        function_name="fetch_recent_game_ids",
        inputs={"team_id": 1610612738},
    )
    assert out == ["1", "2", "3", "4", "5"]


def test_fetch_recent_game_ids_invalid(monkeypatch):
    async def fake_fetch_result_set_rows(client, url, params, preferred_result_set_name=None):
        return [{"Game_ID": "1"}]

    monkeypatch.setattr(nba_stats, "fetch_result_set_rows", fake_fetch_result_set_rows)
    with pytest.raises(InvalidResponseError) as exc:
        run(nba_stats.fetch_recent_game_ids(client=object(), team_id=1610612738))
    trace("fetch_recent_game_ids", {"team_id": 1610612738}, f"raised {type(exc.value).__name__}")


def test_fetch_game_advanced_metrics_success(monkeypatch):
    async def fake_fetch_result_set_rows(client, url, params, preferred_result_set_name=None):
        return [{"TEAM_ID": 1610612738, "OFF_RATING": 110, "DEF_RATING": 108, "PACE": 99}]

    monkeypatch.setattr(nba_stats, "fetch_result_set_rows", fake_fetch_result_set_rows)
    metric = run(
        nba_stats.fetch_game_advanced_metrics(client=object(), game_id="123", team_id=1610612738),
        function_name="fetch_game_advanced_metrics",
        inputs={"game_id": "123", "team_id": 1610612738},
    )
    assert metric.off_rating == 110
    assert metric.def_rating == 108
    assert metric.pace == 99


def test_fetch_game_advanced_metrics_missing_team(monkeypatch):
    async def fake_fetch_result_set_rows(client, url, params, preferred_result_set_name=None):
        return [{"TEAM_ID": 1, "OFF_RATING": 110, "DEF_RATING": 108, "PACE": 99}]

    monkeypatch.setattr(nba_stats, "fetch_result_set_rows", fake_fetch_result_set_rows)
    with pytest.raises(InvalidResponseError) as exc:
        run(nba_stats.fetch_game_advanced_metrics(client=object(), game_id="123", team_id=1610612738))
    trace(
        "fetch_game_advanced_metrics",
        {"game_id": "123", "team_id": 1610612738},
        f"raised {type(exc.value).__name__}",
    )


def test_fetch_recent_game_metrics(monkeypatch):
    async def fake_fetch_recent_game_ids(client, team_id):
        return ["1", "2", "3", "4", "5"]

    async def fake_fetch_game_advanced_metrics(client, game_id, team_id):
        base = float(game_id)
        return GameAdvancedMetrics(off_rating=100 + base, def_rating=95 + base, pace=90 + base)

    monkeypatch.setattr(nba_stats, "fetch_recent_game_ids", fake_fetch_recent_game_ids)
    monkeypatch.setattr(nba_stats, "fetch_game_advanced_metrics", fake_fetch_game_advanced_metrics)

    out = run(
        nba_stats.fetch_recent_game_metrics(client=object(), team_id=1610612738),
        function_name="fetch_recent_game_metrics",
        inputs={"team_id": 1610612738},
    )
    assert len(out) == 5
    assert out[0].off_rating == 101.0


def test_resolved_recent_games_primary_path(monkeypatch):
    async def fake_fetch_recent_game_metrics(client, team_id):
        return [GameAdvancedMetrics(110, 105, 98)] * 5

    monkeypatch.setattr(nba_stats, "fetch_recent_game_metrics", fake_fetch_recent_game_metrics)
    rows = [{"TEAM_NAME": "Boston Celtics", "OFF_RATING": 110, "DEF_RATING": 105, "PACE": 98}]
    out = run(
        nba_stats.resolved_recent_games(
            client=object(),
            team_id=1610612738,
            resolved_name="Boston Celtics",
            advanced_last5_rows=rows,
        ),
        function_name="resolved_recent_games",
        inputs={
            "team_id": 1610612738,
            "resolved_name": "Boston Celtics",
            "advanced_last5_rows": rows,
        },
    )
    assert len(out) == 5
    assert out[0].pace == 98


def test_resolved_recent_games_fallback(monkeypatch):
    async def boom_fetch_recent_game_metrics(client, team_id):
        raise RuntimeError("failed")

    monkeypatch.setattr(nba_stats, "fetch_recent_game_metrics", boom_fetch_recent_game_metrics)
    rows = [{"TEAM_NAME": "Boston Celtics", "OFF_RATING": 110, "DEF_RATING": 105, "PACE": 98}]
    out = run(
        nba_stats.resolved_recent_games(
            client=object(),
            team_id=1610612738,
            resolved_name="Boston Celtics",
            advanced_last5_rows=rows,
        ),
        function_name="resolved_recent_games",
        inputs={
            "team_id": 1610612738,
            "resolved_name": "Boston Celtics",
            "advanced_last5_rows": rows,
        },
    )
    assert len(out) == 5
    assert all(x.off_rating == 110 for x in out)


def test_fetch_team_metrics_success(monkeypatch):
    class DummyAsyncClientCtx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(nba_stats.httpx, "AsyncClient", lambda **kwargs: DummyAsyncClientCtx())

    async def fake_fetch_rows(client, measure_type, last_n_games):
        if measure_type == "Advanced":
            return [{"TEAM_NAME": "Boston Celtics", "OFF_RATING": 111, "DEF_RATING": 107, "PACE": 100}]
        return [
            {"TEAM_NAME": "Boston Celtics", "PCT_PTS_3PT": 0.37},
            {"TEAM_NAME": "New York Knicks", "PCT_PTS_3PT": 0.35},
        ]

    async def fake_resolved_recent_games(client, team_id, resolved_name, advanced_last5_rows):
        return [
            GameAdvancedMetrics(110, 106, 99),
            GameAdvancedMetrics(112, 108, 101),
            GameAdvancedMetrics(111, 107, 100),
            GameAdvancedMetrics(113, 109, 102),
            GameAdvancedMetrics(109, 105, 98),
        ]

    monkeypatch.setattr(nba_stats, "fetch_rows", fake_fetch_rows)
    monkeypatch.setattr(nba_stats, "resolved_recent_games", fake_resolved_recent_games)

    out = run(
        nba_stats.fetch_team_metrics(client=object(), team_name="celtics"),
        function_name="fetch_team_metrics",
        inputs={"team_name": "celtics"},
    )
    assert out.display_name == "Boston Celtics"
    assert out.three_point_pct == 37.0
    assert out.league_average_three_point_pct > 0


def test_fetch_team_metrics_unknown_team():
    with pytest.raises(TeamNotFoundError) as exc:
        run(nba_stats.fetch_team_metrics(client=object(), team_name="not-a-team"))
    trace("fetch_team_metrics", {"team_name": "not-a-team"}, f"raised {type(exc.value).__name__}")


def test_build_projection(monkeypatch):
    async def fake_fetch_team_metrics(client, team):
        return _team_metrics("Boston Celtics" if "boston" in team.lower() else "New York Knicks")

    monkeypatch.setattr(projection, "fetch_team_metrics", fake_fetch_team_metrics)

    out = run(
        projection.build_projection(client=object(), away_team="Boston Celtics", home_team="New York Knicks"),
        function_name="build_projection",
        inputs={"away_team": "Boston Celtics", "home_team": "New York Knicks"},
    )
    assert out["away_team_name"] == "Boston Celtics"
    assert out["home_team_name"] == "New York Knicks"
    assert isinstance(out["projected_total"], float)


def test_basketball_projection_success(monkeypatch):
    async def fake_build_projection(client, away_team, home_team):
        return {"away_team_name": away_team, "home_team_name": home_team, "projected_total": 220.0, "projected_total_std_dev": 10.0, "away": {}, "home": {}, "league": {}}

    monkeypatch.setattr(basketball, "build_projection", fake_build_projection)
    req = ProjectionRequest(away_team="Boston Celtics", home_team="New York Knicks")
    out = run(
        basketball.basketball_projection(req, client=object()),
        function_name="basketball_projection",
        inputs=req.model_dump(),
    )
    assert out["away_team_name"] == "Boston Celtics"


def test_basketball_projection_error(monkeypatch):
    async def fake_build_projection(client, away_team, home_team):
        raise StatsServiceError("service failed")

    monkeypatch.setattr(basketball, "build_projection", fake_build_projection)
    req = ProjectionRequest(away_team="AA", home_team="BB")

    with pytest.raises(HTTPException) as exc:
        run(basketball.basketball_projection(req, client=object()))
    trace("basketball_projection", req.model_dump(), f"raised {type(exc.value).__name__}: {exc.value.detail}")

    assert exc.value.status_code == 400
    assert exc.value.detail == "service failed"


def test_auth_me_route_without_auth_enabled():
    out = run(system.auth_me(token=None), function_name="auth_me", inputs={"token": None})
    assert out == {"authenticated": False, "token_present": False}


def test_require_auth_disabled_is_noop():
    out = run(require_auth(credentials=None), function_name="require_auth", inputs={"credentials": None})
    assert out is None


def test_cors_middleware_registered():
    middleware_names = [m.cls.__name__ for m in main.app.user_middleware]
    assert "CORSMiddleware" in middleware_names


def test_health_endpoint_http_contract():
    client = TestClient(main.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_me_endpoint_http_contract_with_dependency_override():
    async def fake_require_auth():
        return "demo-token"

    main.app.dependency_overrides[require_auth] = fake_require_auth
    try:
        client = TestClient(main.app)
        response = client.get("/api/auth/me")

        assert response.status_code == 200
        assert response.json() == {"authenticated": False, "token_present": True}
    finally:
        main.app.dependency_overrides.clear()


def test_basketball_projection_endpoint_http_contract_success(monkeypatch):
    async def fake_build_projection(client, away_team, home_team):
        return {
            "away_team_name": away_team,
            "home_team_name": home_team,
            "projected_total": 220.0,
            "projected_total_std_dev": 10.0,
            "away": {
                "off_rating": 111.0,
                "def_rating": 107.0,
                "pace": 100.0,
                "three_point_pct": 36.4,
                "three_point_pct_text": "36.4",
            },
            "home": {
                "off_rating": 109.0,
                "def_rating": 108.0,
                "pace": 99.0,
                "three_point_pct": 35.2,
                "three_point_pct_text": "35.2",
            },
            "league": {
                "avg_3pt_pct": 35.8,
                "std_dev_3pt_pct": 2.1,
            },
        }

    monkeypatch.setattr(basketball, "build_projection", fake_build_projection)
    client = TestClient(main.app)
    response = client.post(
        "/api/basketball/projection",
        json={"away_team": "Boston Celtics", "home_team": "New York Knicks"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["away_team_name"] == "Boston Celtics"
    assert body["home_team_name"] == "New York Knicks"
    assert body["projected_total"] == 220.0
    assert body["away"]["off_rating"] == 111.0
    assert body["league"]["avg_3pt_pct"] == 35.8


def test_basketball_projection_endpoint_http_contract_error(monkeypatch):
    async def fake_build_projection(client, away_team, home_team):
        raise StatsServiceError("service failed")

    monkeypatch.setattr(basketball, "build_projection", fake_build_projection)
    client = TestClient(main.app)
    response = client.post(
        "/api/basketball/projection",
        json={"away_team": "Boston Celtics", "home_team": "New York Knicks"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "service failed"}


def test_basketball_projection_endpoint_validation_error_short_team_name():
    client = TestClient(main.app)
    response = client.post(
        "/api/basketball/projection",
        json={"away_team": "A", "home_team": "New York Knicks"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(item["loc"][-1] == "away_team" for item in detail)
