import asyncio
import logging
from datetime import datetime, time, timedelta
from app.services.nba_stats import fetch_team_metrics
from app.utils.team_aliases import TEAM_IDS
from app.api.deps.http_client import ClientManager

logger = logging.getLogger(__name__)

async def prime_cache():
    """Fetches metrics for all teams to prime the cache."""
    logger.info("Starting cache priming...")
    client = ClientManager.get_client()
    teams = list(TEAM_IDS.keys())
    
    # Process teams in chunks to avoid overwhelming the API
    chunk_size = 5
    for i in range(0, len(teams), chunk_size):
        chunk = teams[i:i + chunk_size]
        tasks = [fetch_team_metrics(client, team) for team in chunk]
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(1)  # Rate limiting
    
    logger.info("Cache priming completed.")

async def scheduler():
    """Runs the cache priming task every day at 3:00 AM."""
    while True:
        now = datetime.now()
        target_time = time(3, 0)
        target_datetime = datetime.combine(now.date(), target_time)
        
        if now.time() >= target_time:
            target_datetime += timedelta(days=1)
        
        sleep_seconds = (target_datetime - now).total_seconds()
        logger.info(f"Next cache priming scheduled at {target_datetime} (in {sleep_seconds}s)")
        
        await asyncio.sleep(sleep_seconds)
        try:
            await prime_cache()
        except Exception as e:
            logger.error(f"Error during cache priming: {e}")
