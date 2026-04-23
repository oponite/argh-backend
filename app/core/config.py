import os
from types import SimpleNamespace


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_csv(value: str | None, default: list[str] | None = None) -> list[str]:
    if value is None:
        return default or []
    values = [item.strip() for item in value.split(",")]
    return [item for item in values if item]


APP_NAME = os.getenv("APP_NAME", "Basketball Projection API")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
CORS_ALLOW_ORIGINS = _parse_csv(os.getenv("CORS_ALLOW_ORIGINS"), default=["*"])
AUTH_ENABLED = _parse_bool(os.getenv("AUTH_ENABLED"), default=False)
AUTH_TOKENS = _parse_csv(os.getenv("AUTH_TOKENS"))

NBA_BASE_URL = os.getenv("NBA_BASE_URL", "https://stats.nba.com/stats")
DEFAULT_TIMEOUT = float(os.getenv("DEFAULT_TIMEOUT", "15.0"))
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0")
NBA_HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

# Keep a small settings object because the rest of the app imports settings.*.
settings = SimpleNamespace(
    app_name=APP_NAME,
    app_version=APP_VERSION,
    log_level=LOG_LEVEL,
    cors_allow_origins=CORS_ALLOW_ORIGINS,
    auth_enabled=AUTH_ENABLED,
    auth_tokens=AUTH_TOKENS,
)
