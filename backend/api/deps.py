from typing import Annotated, AsyncIterator

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.session import async_session_factory

# auto_error=False — we handle the "no token" case ourselves
_bearer = HTTPBearer(auto_error=False)

# Origins allowed to call the API without a Bearer token (browser requests)
_TRUSTED_ORIGINS = {
    "http://shorts.v3techbots.online",
    "https://shorts.v3techbots.online",
    "http://185.252.215.53:3000",
    "http://185.252.215.53",
    "http://localhost:3000",
    "http://localhost:8000",
}


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def verify_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)] = None,
) -> str:
    """
    Two-mode auth:
    - Browser requests from _TRUSTED_ORIGINS: no token needed.
    - External API calls: must supply a valid Bearer token.
    """
    settings = get_settings()

    if credentials and credentials.credentials == settings.api_auth_token:
        return credentials.credentials

    # Allow trusted browser origins without a token
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    if origin in _TRUSTED_ORIGINS or any(referer.startswith(o) for o in _TRUSTED_ORIGINS):
        return "browser_request"

    # If a token was provided but wrong
    if credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Authorization required (Bearer token or trusted origin)",
    )


DbSession = Annotated[AsyncSession, Depends(get_db)]
AuthToken = Annotated[str, Depends(verify_token)]
