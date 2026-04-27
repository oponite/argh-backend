import asyncio
from datetime import UTC, datetime
from typing import List, Dict, Any, Optional

import httpx

from app.core.config import NBA_BASE_URL, NBA_HEADERS, DEFAULT_TIMEOUT
from app.core.utils.normalization import normalize
from app.core.utils.team_aliases import TEAM_ALIASES, TEAM_IDS
from app.core.errors import (
    TeamNotFoundError,
    InvalidResponseError,
    RequestFailedError,
)
from app.core.utils.statistics import mean, std_dev
from app.core.utils.cache import cached_fetch_rows, cached_fetch_team_metrics


class GameAdvancedMetrics:
    def __init__(self, off_rating: float, def_rating: float, pace: float):
        self.off_rating = off_rating
        self.def_rating = def_rating
        self.pace = pace

class TeamMetrics:
    def __init__(
        self,
        display_name: str,
        recent_games: List[GameAdvancedMetrics],
        off_rating_mean: float,
        def_rating_mean: float,
        pace_mean: float,
        three_point_pct: float,
        three_point_pct_text: str,
        league_average_three_point_pct: float,
        league_three_point_pct_standard_deviation: float,
    ):
        self.display_name = display_name
        self.recent_games = recent_games
        self.off_rating_mean = off_rating_mean
        self.def_rating_mean = def_rating_mean
        self.pace_mean = pace_mean
        self.three_point_pct = three_point_pct
        self.three_point_pct_text = three_point_pct_text
        self.league_average_three_point_pct = league_average_three_point_pct
        self.league_three_point_pct_standard_deviation = (
            league_three_point_pct_standard_deviation
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "off_rating": self.off_rating_mean,
            "def_rating": self.def_rating_mean,
            "pace": self.pace_mean,
            "three_point_pct": self.three_point_pct,
            "three_point_pct_text": self.three_point_pct_text,
        }

    def league_metrics(self) -> Dict[str, float]:
        return {
            "avg_3pt_pct": self.league_average_three_point_pct,
            "std_dev_3pt_pct": self.league_three_point_pct_standard_deviation,
        }


@cached_fetch_team_metrics
async def fetch_team_metrics(client: httpx.AsyncClient, team_name: str) -> TeamMetrics:
    normalized_input = normalize(team_name)

    if normalized_input not in TEAM_ALIASES:
        raise TeamNotFoundError(team_name)

    resolved_name = TEAM_ALIASES[normalized_input]

    if resolved_name not in TEAM_IDS:
        raise TeamNotFoundError(resolved_name)

    team_id = TEAM_IDS[resolved_name]

    advanced_last5_task = fetch_rows(
        client=client,
        measure_type="Advanced",
        last_n_games=5,
    )

    scoring_rows_task = fetch_rows(
        client=client,
        measure_type="Scoring",
        last_n_games=0,
    )

    advanced_last5_rows, scoring_rows = await asyncio.gather(
        advanced_last5_task,
        scoring_rows_task,
    )

    recent_games = await resolved_recent_games(
        client=client,
        team_id=team_id,
        resolved_name=resolved_name,
        advanced_last5_rows=advanced_last5_rows,
    )

    scoring_row = next(
        (
            row
            for row in scoring_rows
            if matches_team(row, expected_name=resolved_name)
        ),
        None,
    )

    if scoring_row is None:
        raise InvalidResponseError()

    three_point_pct_raw = value_for(
        keys=["PCT_PTS_3PT"], row=scoring_row
    )

    if three_point_pct_raw is None:
        raise InvalidResponseError()

    off_values = [g.off_rating for g in recent_games]
    def_values = [g.def_rating for g in recent_games]
    pace_values = [g.pace for g in recent_games]

    off_rating_mean = mean(off_values)
    def_rating_mean = mean(def_values)
    pace_mean = mean(pace_values)

    league_three_point_values: List[float] = []
    for row in scoring_rows:
        raw = value_for(["PCT_PTS_3PT"], row)
        if raw is not None:
            league_three_point_values.append(
                raw * 100 if raw <= 1 else raw
            )

    league_avg_three_point_pct = mean(league_three_point_values)
    league_three_point_std_dev = std_dev(league_three_point_values)

    three_point_pct = (
        three_point_pct_raw * 100
        if three_point_pct_raw <= 1
        else three_point_pct_raw
    )

    three_point_pct_text = format_percentage_text(three_point_pct)

    return TeamMetrics(
        display_name=resolved_name,
        recent_games=recent_games,
        off_rating_mean=off_rating_mean,
        def_rating_mean=def_rating_mean,
        pace_mean=pace_mean,
        three_point_pct=three_point_pct,
        three_point_pct_text=three_point_pct_text,
        league_average_three_point_pct=league_avg_three_point_pct,
        league_three_point_pct_standard_deviation=league_three_point_std_dev,
    )



async def resolved_recent_games(
    client: httpx.AsyncClient,
    team_id: int,
    resolved_name: str,
    advanced_last5_rows: List[Dict[str, Any]],
) -> List[GameAdvancedMetrics]:

    try:
        return await fetch_recent_game_metrics(
            client=client,
            team_id=team_id,
        )

    except Exception:
        advanced_row = next(
            (
                row
                for row in advanced_last5_rows
                if matches_team(row, expected_name=resolved_name)
            ),
            None,
        )

        if advanced_row is None:
            raise InvalidResponseError()

        off_rating = value_for(["OFF_RATING"], advanced_row)
        def_rating = value_for(["DEF_RATING"], advanced_row)
        pace = value_for(["PACE"], advanced_row)

        if off_rating is None or def_rating is None or pace is None:
            raise InvalidResponseError()

        fallback_game = GameAdvancedMetrics(
            off_rating=off_rating,
            def_rating=def_rating,
            pace=pace,
        )

        return [fallback_game] * 5



async def fetch_recent_game_metrics(
    client: httpx.AsyncClient,
    team_id: int,
) -> List[GameAdvancedMetrics]:

    recent_game_ids = await fetch_recent_game_ids(
        client=client,
        team_id=team_id,
    )

    tasks = [
        fetch_game_advanced_metrics(
            client=client,
            game_id=game_id,
            team_id=team_id,
        )
        for game_id in recent_game_ids
    ]

    return list(await asyncio.gather(*tasks))



async def fetch_recent_game_ids(
    client: httpx.AsyncClient,
    team_id: int,
) -> List[str]:

    url = f"{NBA_BASE_URL}/teamgamelog"

    params = {
        "DateFrom": "",
        "DateTo": "",
        "LeagueID": "00",
        "Season": current_season_string(),
        "SeasonType": "Regular Season",
        "TeamID": str(team_id),
    }

    rows = await fetch_result_set_rows(
        client=client,
        url=url,
        params=params,
    )

    recent_game_ids: List[str] = []

    for row in rows[:5]:
        game_id = row.get("Game_ID")
        if isinstance(game_id, str):
            recent_game_ids.append(game_id)
        elif isinstance(game_id, (int, float)):
            recent_game_ids.append(str(int(game_id)))

    if len(recent_game_ids) != 5:
        raise InvalidResponseError()

    return recent_game_ids


async def fetch_game_advanced_metrics(
    client: httpx.AsyncClient,
    game_id: str,
    team_id: int,
) -> GameAdvancedMetrics:

    url = f"{NBA_BASE_URL}/boxscoreadvancedv2"

    params = {
        "EndPeriod": "10",
        "EndRange": "28800",
        "GameID": game_id,
        "RangeType": "0",
        "StartPeriod": "1",
        "StartRange": "0",
    }

    rows = await fetch_result_set_rows(
        client=client,
        url=url,
        params=params,
        preferred_result_set_name="TeamStats",
    )

    row = next(
        (
            r
            for r in rows
            if row_matches_team_id(r, team_id=team_id)
        ),
        None,
    )

    if row is None:
        raise InvalidResponseError()

    off_rating = value_for(["OFF_RATING"], row)
    def_rating = value_for(["DEF_RATING"], row)
    pace = value_for(["PACE"], row)

    if off_rating is None or def_rating is None or pace is None:
        raise InvalidResponseError()

    return GameAdvancedMetrics(
        off_rating=off_rating,
        def_rating=def_rating,
        pace=pace,
    )


@cached_fetch_rows
async def fetch_rows(
    client: httpx.AsyncClient,
    measure_type: str,
    last_n_games: int,
) -> List[Dict[str, Any]]:

    url = f"{NBA_BASE_URL}/leaguedashteamstats"

    params = query_items(
        measure_type=measure_type,
        last_n_games=last_n_games,
    )

    return await fetch_result_set_rows(
        client=client,
        url=url,
        params=params,
    )


async def fetch_result_set_rows(
    client: httpx.AsyncClient,
    url: str,
    params: Dict[str, str],
    preferred_result_set_name: Optional[str] = None,
) -> List[Dict[str, Any]]:

    delays = [0.0, 0.4, 1.0]
    last_error: Optional[Exception] = None

    for delay in delays:
        if delay > 0:
            await asyncio.sleep(delay)

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()

            payload = response.json()
            result_sets = payload.get("resultSets")

            if not isinstance(result_sets, list):
                raise InvalidResponseError()

            if preferred_result_set_name:
                selected_set = next(
                    (
                        rs
                        for rs in result_sets
                        if rs.get("name", "").lower()
                        == preferred_result_set_name.lower()
                    ),
                    None,
                )
                if selected_set is None:
                    raise InvalidResponseError()
            else:
                selected_set = result_sets[0]

            headers = selected_set.get("headers")
            row_set = selected_set.get("rowSet")

            if not headers or not row_set:
                raise InvalidResponseError()

            return [
                dict(zip(headers, row))
                for row in row_set
            ]

        except Exception as e:
            last_error = e

    raise RequestFailedError() from last_error


def matches_team(row: Dict[str, Any], expected_name: str) -> bool:
    row_name = normalize(str(row.get("TEAM_NAME", "")))
    return row_name == normalize(expected_name)


def row_matches_team_id(row: Dict[str, Any], team_id: int) -> bool:
    value = row.get("TEAM_ID")
    if isinstance(value, (int, float)):
        return int(value) == team_id
    if isinstance(value, str):
        return value.isdigit() and int(value) == team_id
    return False


def value_for(keys: List[str], row: Dict[str, Any]) -> Optional[float]:
    for key in keys:
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                pass
    return None


def format_percentage_text(value: float) -> str:
    text = f"{value:.1f}"
    return text.rstrip("0").rstrip(".")


def current_season_string() -> str:
    now = datetime.now(UTC)
    year = now.year
    month = now.month
    start_year = year if month >= 7 else year - 1
    end_year = (start_year + 1) % 100
    return f"{start_year}-{end_year:02d}"


def query_items(
    measure_type: str,
    last_n_games: int,
) -> Dict[str, str]:
    return {
        "College": "",
        "Conference": "",
        "Country": "",
        "DateFrom": "",
        "DateTo": "",
        "Division": "",
        "GameScope": "",
        "GameSegment": "",
        "Height": "",
        "ISTRound": "",
        "LastNGames": str(last_n_games),
        "LeagueID": "00",
        "Location": "",
        "MeasureType": measure_type,
        "Month": "0",
        "OpponentTeamID": "0",
        "Outcome": "",
        "PORound": "0",
        "PaceAdjust": "N",
        "PerMode": "PerPossession",
        "Period": "0",
        "PlayerExperience": "",
        "PlayerPosition": "",
        "PlusMinus": "N",
        "Rank": "N",
        "Season": current_season_string(),
        "SeasonSegment": "",
        "SeasonType": "Regular Season",
        "ShotClockRange": "",
        "StarterBench": "",
        "TeamID": "0",
        "TwoWay": "0",
        "VsConference": "",
        "VsDivision": "",
        "Weight": "",
    }
