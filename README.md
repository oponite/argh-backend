# ARGH Backend

FastAPI backend designed to serve multiple clients (iOS + web) from one API surface for A Really Good Helper.

## Inclusions

- FastAPI app with health check and namespaced routes under `/api`
- CORS middleware configured via environment variables
- Env-driven settings (`app/core/config.py`)
- Starter bearer-token auth dependency (`app/api/deps/auth.py`)
- Domain endpoint: `POST /api/basketball/projection`
- Auth endpoint:
  - `GET /api/auth/me`
- Test suite with API + service coverage