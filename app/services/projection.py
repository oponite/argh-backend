import numpy as np
from app.services.nba_stats import fetch_team_metrics
from app.utils.statistics import classify_z_score


# TODO: add redis dependency to reduce # of API calls

async def build_projection(away_team, home_team, bookie_total):
    away = await fetch_team_metrics(away_team)
    home = await fetch_team_metrics(home_team)

    weights = np.linspace(0.5, 0.8, 10_000)

    away_off = np.array([g.off_rating for g in away.recent_games])
    away_def = np.array([g.def_rating for g in away.recent_games])
    away_pace = np.array([g.pace for g in away.recent_games])

    home_off = np.array([g.off_rating for g in home.recent_games])
    home_def = np.array([g.def_rating for g in home.recent_games])
    home_pace = np.array([g.pace for g in home.recent_games])

    avg_pace = (away_pace[:, None] + home_pace[None, :]) / 2

    away_component = (
            weights[:, None, None]
            * away_off[None, :, None]
            + (1 - weights[:, None, None])
            * home_def[None, None, :]
    )

    home_component = (
            weights[:, None, None]
            * home_off[None, None, :]
            + (1 - weights[:, None, None])
            * away_def[None, :, None]
    )

    totals = ((away_component + home_component) / 100) * avg_pace

    totals_flat = totals.reshape(-1)

    projected_total = float(np.mean(totals_flat))
    std_dev = float(np.std(totals_flat)) or 1e-6

    z_score = (projected_total - bookie_total) / std_dev

    return {
        "away_team_name": away.display_name,
        "home_team_name": home.display_name,
        "projected_total": projected_total,
        "projected_total_std_dev": std_dev,
        "totals_z_score": z_score,
        "totals_classification": classify_z_score(z_score),
        "away": away.as_dict(),
        "home": home.as_dict(),
        "league": away.league_metrics(),
    }