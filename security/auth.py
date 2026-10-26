from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from utils.jwt import decode_token


bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Invalid or expired access token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Bearer access token is required")

    try:
        payload = decode_token(credentials.credentials, "access")
        user_id = int(payload["sub"])
    except (PyJWTError, KeyError, TypeError, ValueError):
        raise _unauthorized() from None
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from exc

    try:
        current_user = db.execute(
            text(
                """
                SELECT id, username, email, person_id, role_id, is_active, created_at
                FROM users
                WHERE id = :user_id
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="User service unavailable") from exc

    if not current_user:
        raise _unauthorized()
    current_user = dict(current_user)
    if not current_user.get("is_active", False):
        raise HTTPException(status_code=403, detail="User account is inactive")

    return current_user


def require_admin(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    role_id = current_user.get("role_id")
    if role_id is None:
        raise HTTPException(status_code=403, detail="User has no role assigned")

    try:
        role = db.execute(
            text("SELECT role_id, role_name FROM roles WHERE role_id = :role_id LIMIT 1"),
            {"role_id": role_id},
        ).mappings().first()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Authorization service unavailable") from exc

    if not role:
        raise HTTPException(status_code=403, detail="User role not found")

    role_name = str(role.get("role_name", "")).strip().lower()
    if role_name != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")

    current_user["role"] = role_name
    return current_user


def require_staff(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    role_id = current_user.get("role_id")
    if role_id is None:
        raise HTTPException(status_code=403, detail="User has no role assigned")

    try:
        role = db.execute(
            text("SELECT role_name FROM roles WHERE role_id = :role_id LIMIT 1"),
            {"role_id": role_id},
        ).mappings().first()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Authorization service unavailable") from exc

    role_name = str(role.get("role_name", "")).strip().lower() if role else ""
    if role_name not in {"staff", "teacher"}:
        raise HTTPException(status_code=403, detail="Staff access required")

    person_id = current_user.get("person_id")
    if person_id is None:
        raise HTTPException(status_code=403, detail="User is not linked to a staff profile")

    try:
        staff = db.execute(
            text(
                """
                SELECT id
                FROM staff
                WHERE id = :staff_id
                  AND LOWER(status) = 'active'
                LIMIT 1
                """
            ),
            {"staff_id": person_id},
        ).first()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Authorization service unavailable") from exc

    if not staff:
        raise HTTPException(status_code=403, detail="Staff profile is missing or inactive")

    current_user["role"] = "staff"
    return current_user


def require_student(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    person_id = current_user.get("person_id")
    if person_id is None:
        raise HTTPException(status_code=403, detail="Student account is not linked to a student")

    try:
        student = db.execute(
            text(
                """
                SELECT s.id
                FROM users u
                JOIN roles r ON r.role_id = u.role_id
                JOIN students s ON s.id = u.person_id
                WHERE u.id = :user_id
                  AND LOWER(r.role_name) = 'student'
                  AND LOWER(s.status) = 'active'
                LIMIT 1
                """
            ),
            {"user_id": current_user["id"]},
        ).first()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Authorization service unavailable") from exc

    if not student:
        raise HTTPException(status_code=403, detail="Active student access required")

    current_user["role"] = "student"
    return current_user


def require_admin_staff_or_student(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        role = db.execute(
            text("SELECT role_name FROM roles WHERE role_id = :role_id LIMIT 1"),
            {"role_id": current_user.get("role_id")},
        ).mappings().first()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Authorization service unavailable") from exc

    role_name = str(role.get("role_name", "")).strip().lower() if role else ""
    if role_name == "admin":
        current_user["role"] = "admin"
        return current_user
    if role_name in {"staff", "teacher"}:
        return require_staff(current_user, db)
    if role_name == "student":
        return require_student(current_user, db)
    raise HTTPException(status_code=403, detail="Access denied")


def require_admin_or_staff(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    role_id = current_user.get("role_id")
    if role_id is None:
        raise HTTPException(status_code=403, detail="User has no role assigned")

    try:
        role = db.execute(
            text("SELECT role_name FROM roles WHERE role_id = :role_id LIMIT 1"),
            {"role_id": role_id},
        ).mappings().first()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Authorization service unavailable") from exc

    role_name = str(role.get("role_name", "")).strip().lower() if role else ""
    if role_name == "admin":
        current_user["role"] = "admin"
        return current_user

    return require_staff(current_user, db)
