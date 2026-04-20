NBA_BASE_URL = "https://stats.nba.com/stats"

DEFAULT_TIMEOUT = 15.0
USER_AGENT = "Mozilla/5.0"
NBA_HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}