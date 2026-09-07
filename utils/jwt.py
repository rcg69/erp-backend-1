import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)


def _get_secret_key() -> str:
    if not SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured")
    return SECRET_KEY


def create_access_token(*, user_id: int, person_id: int | None, role_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "person_id": person_id,
        "role_id": role_id,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        _get_secret_key(),
        algorithms=[ALGORITHM],
        options={"require": ["sub", "iat", "exp"]},
    )