from fastapi import APIRouter, Depends

from app.api.deps.auth import require_auth
from app.core.config import settings

router = APIRouter()


@router.get("/auth/me", tags=["auth"])
async def auth_me(token: str | None = Depends(require_auth)):
    # Informs if auth is turned on and whether this request included a valid token.
    return {
        "authenticated": settings.auth_enabled,
        "token_present": bool(token),
    }