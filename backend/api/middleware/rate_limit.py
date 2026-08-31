"""Rate-limit configuration and request key functions."""

from fastapi import Request
from jose import JWTError
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.auth_service import decode_jwt

# In-memory counters are intentionally acceptable for the current single-instance deployment.
# They reset on restart and must be replaced before horizontally scaling the API.
limiter = Limiter(key_func=get_remote_address)


def get_user_key(request: Request) -> str:
    """Key authenticated limits by signed JWT subject, falling back to client IP."""
    token = request.cookies.get("access_token")
    if token:
        try:
            subject = decode_jwt(token).get("sub")
            if subject:
                return f"user:{subject}"
        except JWTError:
            pass
    return f"ip:{get_remote_address(request)}"
