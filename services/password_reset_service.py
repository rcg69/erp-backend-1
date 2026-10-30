import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import auth_model
from services.email_service import send_password_reset_email
from services.password_service import hash_password


logger = logging.getLogger(__name__)
RESET_TOKEN_TTL = timedelta(minutes=30)
GENERIC_REQUEST_MESSAGE = "If an account exists for that email, a password reset link has been sent."


def _token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(email: str, db: Session) -> dict:
    normalized_email = email.strip().lower()
    user = auth_model.get_user_by_email(db, normalized_email)
    if not user or not user.get("is_active", False):
        return {"success": True, "message": GENERIC_REQUEST_MESSAGE}

    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + RESET_TOKEN_TTL
    try:
        auth_model.create_password_reset_token(
            db, user["id"], _token_hash(raw_token), expires_at
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Password reset token could not be stored")
        raise HTTPException(status_code=503, detail="Password reset is temporarily unavailable") from None

    frontend_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
    reset_url = f"{frontend_url}/reset-password?{urlencode({'token': raw_token})}"
    try:
        send_password_reset_email(normalized_email, reset_url)
    except Exception:
        # Keep the response identical for known and unknown accounts.
        logger.exception("Password reset email delivery failed")

    return {"success": True, "message": GENERIC_REQUEST_MESSAGE}


def confirm_password_reset(token: str, new_password: str, db: Session) -> dict:
    try:
        user_id = auth_model.consume_password_reset_token(db, _token_hash(token))
        if user_id is None:
            db.rollback()
            raise HTTPException(status_code=400, detail="Reset token is invalid or expired")

        auth_model.update_user_password(db, user_id, hash_password(new_password))
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Password reset could not be completed")
        raise HTTPException(status_code=503, detail="Password reset is temporarily unavailable") from None

    return {"success": True, "message": "Password updated. You can now sign in."}
