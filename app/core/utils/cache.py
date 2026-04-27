from cachetools import TTLCache
from datetime import datetime, timedelta, time
import asyncio
from functools import wraps

class EODCache(TTLCache):
    """A cache that expires at the end of the day."""
    def __init__(self, maxsize):
        super().__init__(maxsize=maxsize, ttl=86400)

    def _get_ttl_to_eod(self):
        now = datetime.now()
        eod = datetime.combine(now.date() + timedelta(days=1), time.min)
        return (eod - now).total_seconds()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)

# Cache for fetch_rows (league-wide data)
rows_cache = EODCache(maxsize=10)
# Cache for fetch_team_metrics (team-specific data)
metrics_cache = EODCache(maxsize=100)

def cached_fetch_rows(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Create a cache key from relevant kwargs
        key = (kwargs.get('measure_type'), kwargs.get('last_n_games'))
        if key in rows_cache:
            return rows_cache[key]
        result = await func(*args, **kwargs)
        rows_cache[key] = result
        return result
    return wrapper

def cached_fetch_team_metrics(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # args[1] is team_name if called as fetch_team_metrics(client, team_name)
        team_name = args[1] if len(args) > 1 else kwargs.get('team_name')
        if team_name in metrics_cache:
            return metrics_cache[team_name]
        result = await func(*args, **kwargs)
        metrics_cache[team_name] = result
        return result
    return wrapper
