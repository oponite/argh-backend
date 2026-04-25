import numpy as np
from app.services.nba_stats import fetch_team_metrics
import httpx

# Precompute constants
WEIGHTS = np.linspace(0.5, 0.8, 10_000)
ONE_MINUS_WEIGHTS = 1 - WEIGHTS

async def build_projection(client: httpx.AsyncClient, away_team, home_team):
    away = await fetch_team_metrics(client, away_team)
    home = await fetch_team_metrics(client, home_team)

    away_off = np.array([g.off_rating for g in away.recent_games])
    away_def = np.array([g.def_rating for g in away.recent_games])
    away_pace = np.array([g.pace for g in away.recent_games])

    home_off = np.array([g.off_rating for g in home.recent_games])
    home_def = np.array([g.def_rating for g in home.recent_games])
    home_pace = np.array([g.pace for g in home.recent_games])

    # avg_pace is (5, 5) array
    avg_pace = (away_pace[:, None] + home_pace[None, :]) / 2

    # Vectorized computation using precomputed weights
    # away_component: (10000, 5, 5)
    away_component = (
            WEIGHTS[:, None, None] * away_off[None, :, None]
            + ONE_MINUS_WEIGHTS[:, None, None] * home_def[None, None, :]
    )

    # home_component: (10000, 5, 5)
    home_component = (
            WEIGHTS[:, None, None] * home_off[None, None, :]
            + ONE_MINUS_WEIGHTS[:, None, None] * away_def[None, :, None]
    )

    # totals: (10000, 5, 5)
    totals = ((away_component + home_component) / 100) * avg_pace[None, :, :]

    projected_total = float(np.mean(totals))
    std_dev = float(np.std(totals)) or 1e-6

    return {
        "away_team_name": away.display_name,
        "home_team_name": home.display_name,
        "projected_total": projected_total,
        "projected_total_std_dev": std_dev,
        "away": away.as_dict(),
        "home": home.as_dict(),
        "league": away.league_metrics(),
    }