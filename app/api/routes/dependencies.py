"""Shared dependencies for API routes."""
from fastapi import HTTPException, Header
from app.config.settings import get_settings
from app.security import verify_token

settings = get_settings()


async def get_current_user_id(
    authorization: str | None = Header(None, alias="Authorization"),
) -> int:
    """Get current user ID from JWT token.

    For MVP: Falls back to default_user_id if no token provided.

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")

    Returns:
        User ID from token or default user ID

    Raises:
        HTTPException: If token is invalid
    """
    if not authorization:
        return settings.default_user_id

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme",
            )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format",
        )

    user_id = verify_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    return user_id
