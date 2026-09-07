from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError

from database import supabase_admin
from utils.jwt import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Invalid or expired access token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Bearer access token is required")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (PyJWTError, KeyError, TypeError, ValueError):
        raise _unauthorized() from None
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from exc

    try:
        response = (
            supabase_admin.table("users")
            .select("id, username, email, person_id, role_id, is_active, created_at")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="User service unavailable") from exc

    current_user = response.data
    if not current_user:
        raise _unauthorized()
    if not current_user.get("is_active", False):
        raise HTTPException(status_code=403, detail="User account is inactive")

    return current_user


def require_admin(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    try:
        role_response = (
            supabase_admin.table("roles")
            .select("name")
            .eq("id", current_user["role_id"])
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Authorization service unavailable") from exc

    if not role_response.data or role_response.data.get("name", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")

    current_user["role"] = role_response.data["name"]
    return current_user