import os
import traceback
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from schemas.auth_schema import LoginRequest, LoginResponse, RefreshResponse
from schemas.user_schema import UserResponse
from security.auth import get_current_user
from service.password_service import verify_password
from utils.jwt import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)


router = APIRouter(prefix="/api/auth", tags=["Authentication"])
REFRESH_COOKIE_NAME = "refresh_token"
COOKIE_SECURE = os.getenv("JWT_COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("JWT_COOKIE_SAMESITE", "lax")


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/api/auth",
    )


def _store_refresh_token(db: Session, user_id: int, refresh_token: str) -> None:
    payload = decode_token(refresh_token, "refresh")
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    db.execute(
        text(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES (:user_id, :token_hash, :expires_at)
            """
        ),
        {
            "user_id": user_id,
            "token_hash": hash_refresh_token(refresh_token),
            "expires_at": expires_at,
        },
    )


def _get_active_user(db: Session, user_id: int) -> dict:
    user = db.execute(
        text(
            """
            SELECT id, username, email, person_id, role_id, is_active
            FROM users
            WHERE id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = dict(user)
    if not user.get("is_active", False):
        raise HTTPException(status_code=403, detail="User account is inactive")
    return user


@router.get("/me", response_model=UserResponse)
def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/login", response_model=LoginResponse)
def login(
    credentials: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email = str(credentials.email).strip().lower()
    print(
        "[LOGIN] Request received:",
        {"email": email, "password_provided": bool(credentials.password), "password_length": len(credentials.password)},
    )

    try:
        user = db.execute(
            text(
                """
                SELECT id, username, email, person_id, role_id, is_active, password_hash
                FROM users
                WHERE email = :email
                LIMIT 1
                """
            ),
            {"email": email},
        ).mappings().first()
    except Exception as exc:
        print("[LOGIN] Local database lookup failed:", type(exc).__name__, str(exc))
        traceback.print_exc()
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from exc

    user = dict(user) if user else None
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active", False):
        raise HTTPException(status_code=403, detail="User account is inactive")

    try:
        access_token = create_access_token(
            user_id=user["id"],
            person_id=user.get("person_id"),
            role_id=user["role_id"],
        )
        refresh_token = create_refresh_token(user_id=user["id"])
        _store_refresh_token(db, user["id"], refresh_token)
        db.commit()
        _set_refresh_cookie(response, refresh_token)
    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Authentication is not configured") from exc
    except Exception as exc:
        db.rollback()
        print("[LOGIN] Token creation failed:", type(exc).__name__, str(exc))
        traceback.print_exc()
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from exc

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


@router.post("/refresh", response_model=RefreshResponse)
def refresh_access_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    token = refresh_token
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token is required")

    try:
        payload = decode_token(token, "refresh")
        user_id = int(payload["sub"])
        token_hash = hash_refresh_token(token)
        stored = db.execute(
            text(
                """
                SELECT id FROM refresh_tokens
                WHERE token_hash = :token_hash
                  AND user_id = :user_id
                  AND revoked = FALSE
                  AND expires_at > CURRENT_TIMESTAMP
                LIMIT 1
                """
            ),
            {"token_hash": token_hash, "user_id": user_id},
        ).mappings().first()
        if not stored:
            raise HTTPException(status_code=401, detail="Refresh token has been revoked or expired")

        user = _get_active_user(db, user_id)
        db.execute(
            text("UPDATE refresh_tokens SET revoked = TRUE WHERE id = :token_id"),
            {"token_id": stored["id"]},
        )
        new_access_token = create_access_token(
            user_id=user["id"],
            person_id=user.get("person_id"),
            role_id=user["role_id"],
        )
        new_refresh_token = create_refresh_token(user_id=user["id"])
        _store_refresh_token(db, user["id"], new_refresh_token)
        db.commit()
        _set_refresh_cookie(response, new_refresh_token)
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    except HTTPException:
        db.rollback()
        raise
    except (jwt.PyJWTError, KeyError, TypeError, ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token") from exc
    except Exception as exc:
        db.rollback()
        print("[AUTH REFRESH] Failed:", type(exc).__name__, str(exc))
        traceback.print_exc()
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from exc


@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    if refresh_token:
        db.execute(
            text("UPDATE refresh_tokens SET revoked = TRUE WHERE token_hash = :token_hash"),
            {"token_hash": hash_refresh_token(refresh_token)},
        )
        db.commit()
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/auth")
    return {"success": True, "message": "Logged out successfully"}
