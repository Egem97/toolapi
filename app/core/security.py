from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import APIError

_bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(days=settings.JWT_ACCESS_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.APP_NAME,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.APP_NAME,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except JWTError as exc:
        raise APIError(
            code="INVALID_TOKEN",
            message="Invalid or expired token",
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc


async def get_current_client(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError(
            code="UNAUTHORIZED",
            message="Missing bearer token",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    # Only validates signature, issuer and expiry — no credential lookup needed.
    payload = decode_token(credentials.credentials)
    return payload["sub"]
