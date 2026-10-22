
import logging
import os
from datetime import datetime, timezone

import jwt
from fastapi import HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models import auth_model
from schemas.auth_schema import LoginRequest
from services.password_service import verify_password
from utils.jwt import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)


logger = logging.getLogger(__name__)

REFRESH_COOKIE_NAME = "refresh_token"

_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
_SECURE_SETTING = os.getenv("JWT_COOKIE_SECURE")

COOKIE_SECURE = (
    _SECURE_SETTING.lower() == "true"
    if _SECURE_SETTING is not None
    else _ENVIRONMENT in {"production", "prod"}
)

COOKIE_SAMESITE = os.getenv(
    "JWT_COOKIE_SAMESITE", "lax"
).lower()

if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    raise RuntimeError("Invalid JWT_COOKIE_SAMESITE configuration")

if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
    raise RuntimeError("SameSite=None requires secure cookies")


def set_refresh_cookie(
    response: Response,
    refresh_token: str,
) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/api/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/auth",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )


def store_refresh_token(
    db: Session,
    user_id: int,
    refresh_token: str,
) -> None:
    payload = decode_token(refresh_token, "refresh")

    expires_at = datetime.fromtimestamp(
        payload["exp"],
        tz=timezone.utc,
    )

    auth_model.create_refresh_token_record(
        db=db,
        user_id=user_id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=expires_at,
    )


def get_active_user(
    db: Session,
    user_id: int,
) -> dict:
    user = auth_model.get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )

    if not user.get("is_active", False):
        raise HTTPException(
            status_code=403,
            detail="User account is inactive",
        )

    return user


def login(
    credentials: LoginRequest,
    response: Response,
    db: Session,
) -> dict:
    email = str(credentials.email).strip().lower()

    try:
        user = auth_model.get_user_by_email(db, email)
    except SQLAlchemyError:
        db.rollback()
        logger.error("Login database lookup failed")
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        ) from None

    if not user or not user.get("password_hash"):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    try:
        password_valid = verify_password(
            credentials.password,
            user["password_hash"],
        )
    except Exception:
        logger.error("Password verification failed")
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        ) from None

    if not password_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    if not user.get("is_active", False):
        raise HTTPException(
            status_code=403,
            detail="User account is inactive",
        )

    try:
        access_token = create_access_token(
            user_id=user["id"],
            person_id=user.get("person_id"),
            role_id=user["role_id"],
        )

        refresh_token = create_refresh_token(
            user_id=user["id"],
        )

        store_refresh_token(
            db,
            user["id"],
            refresh_token,
        )

        db.commit()
        set_refresh_cookie(response, refresh_token)

    except Exception:
        db.rollback()
        clear_refresh_cookie(response)
        logger.error("Login token issuance failed")

        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        ) from None

    return {
        "success": True,
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "person_id": user.get("person_id"),
            "role_id": user["role_id"],
            "is_active": user["is_active"],
        },
    }


def refresh_access_token(
    response: Response,
    refresh_token: str | None,
    db: Session,
) -> dict:
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Refresh token is required",
        )

    try:
        payload = decode_token(refresh_token, "refresh")
        user_id = int(payload["sub"])
        token_hash = hash_refresh_token(refresh_token)

        stored = auth_model.get_valid_refresh_token(
            db,
            token_hash,
            user_id,
        )

        if not stored:
            raise HTTPException(
                status_code=401,
                detail="Refresh token has been revoked or expired",
            )

        user = get_active_user(db, user_id)

        # Atomically revoke the old token to prevent reuse.
        claimed = auth_model.revoke_refresh_token_by_id(
            db,
            stored["id"],
        )

        if not claimed:
            db.rollback()
            raise HTTPException(
                status_code=401,
                detail="Refresh token has already been used",
            )

        new_access_token = create_access_token(
            user_id=user["id"],
            person_id=user.get("person_id"),
            role_id=user["role_id"],
        )

        new_refresh_token = create_refresh_token(
            user_id=user["id"],
        )

        store_refresh_token(
            db,
            user["id"],
            new_refresh_token,
        )

        # Commit revocation and replacement together.
        db.commit()

        set_refresh_cookie(response, new_refresh_token)

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    except HTTPException:
        db.rollback()
        raise

    except (
        jwt.PyJWTError,
        KeyError,
        TypeError,
        ValueError,
    ):
        db.rollback()
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token",
        ) from None

    except SQLAlchemyError:
        db.rollback()
        logger.error("Refresh token database operation failed")
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        ) from None

    except Exception:
        db.rollback()
        logger.error("Refresh token rotation failed")
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        ) from None


def logout(
    response: Response,
    refresh_token: str | None,
    db: Session,
) -> dict:
    try:
        if refresh_token:
            auth_model.revoke_refresh_token(
                db,
                hash_refresh_token(refresh_token),
            )

        db.commit()

    except Exception:
        db.rollback()
        clear_refresh_cookie(response)
        logger.error("Logout token revocation failed")

        raise HTTPException(
            status_code=503,
            detail="Logout could not be completed",
        ) from None

    clear_refresh_cookie(response)

    return {
        "success": True,
        "message": "Logged out successfully",
    }
