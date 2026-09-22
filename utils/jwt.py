import os
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import jwt
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def _get_secret_key() -> str:
    if not SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured")
    return SECRET_KEY


def create_access_token(*, user_id: int, person_id: int | None, role_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "person_id": person_id,
        "role_id": role_id,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def create_refresh_token(*, user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(
        token,
        _get_secret_key(),
        algorithms=[ALGORITHM],
        options={"require": ["sub", "iat", "exp", "type"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()