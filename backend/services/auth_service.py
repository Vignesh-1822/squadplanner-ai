"""Auth business logic — hashing, JWT, Google token verification."""

from datetime import datetime, timedelta, timezone

import bcrypt
import httpx
from jose import JWTError, jwt

from config import settings

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_jwt(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Raises JWTError if invalid or expired."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])


async def verify_google_token(id_token_str: str) -> dict:
    """Verify a Google ID token via Google's tokeninfo endpoint and return its claims."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token_str},
        )

    if resp.status_code != 200:
        raise ValueError(f"Google token verification failed: {resp.text}")

    claims = resp.json()

    if claims.get("aud") != settings.google_client_id:
        raise ValueError("Token audience does not match client ID")

    return claims
