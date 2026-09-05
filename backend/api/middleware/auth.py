"""FastAPI dependency that validates the JWT cookie and returns the current user."""

from fastapi import Cookie, HTTPException, status
from jose import JWTError

from db.client import get_collection
from services.auth_service import decode_jwt


async def get_current_user(access_token: str | None = Cookie(default=None)) -> dict:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_jwt(access_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    users = get_collection("users")
    user = await users.find_one({"_id": user_id}, {"hashed_password": 0, "_id": 0})

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if payload.get("token_version", 0) != user.get("token_version", 0):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked")

    # Legacy user documents predate both fields; preserve their existing sessions safely.
    user.setdefault("token_version", 0)
    user.setdefault("is_admin", False)
    return user
