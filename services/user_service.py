
import logging

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from models import user_model
from schemas.user_schema import UserCreate
from services.password_service import hash_password


logger = logging.getLogger(__name__)

ALLOWED_ROLES = {"admin", "student", "staff", "teacher"}


def _duplicate_error(exc: IntegrityError) -> HTTPException:
    message = str(exc.orig).lower()

    if "email" in message:
        detail = "Email already exists"
    elif "username" in message:
        detail = "Username already exists"
    else:
        detail = "Email or username already exists"

    return HTTPException(status_code=409, detail=detail)


def _build_payload(user: UserCreate, role: dict) -> dict:
    return {
        "email": str(user.email).strip().lower(),
        "username": user.username.strip(),
        "password_hash": hash_password(user.password),
        "role_id": role["role_id"],
        "person_id": user.person_id,
    }


def _validate_role_and_person(
    db: Session,
    user: UserCreate,
) -> dict:
    role_name = user.role.strip().lower()

    if role_name not in ALLOWED_ROLES:
        raise HTTPException(status_code=422, detail="Invalid role")

    role = user_model.get_role(db, role_name)

    if not role:
        raise HTTPException(status_code=422, detail="Invalid role")

    if not user_model.person_exists(db, role_name, user.person_id):
        if role_name == "student":
            detail = "person_id must reference an existing student"
        else:
            detail = "person_id must reference an existing staff member"

        raise HTTPException(status_code=422, detail=detail)

    return role


def get_users(db: Session) -> list[dict]:
    try:
        return user_model.get_all_users(db)
    except SQLAlchemyError as exc:
        logger.exception("Database error while fetching users")
        raise HTTPException(
            status_code=503,
            detail="User service unavailable",
        ) from exc


def get_user(user_id: int, db: Session) -> dict:
    try:
        user = user_model.get_user_by_id(db, user_id)

        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        logger.exception("Database error while fetching user %s", user_id)
        raise HTTPException(
            status_code=503,
            detail="User service unavailable",
        ) from exc


def create_user(user: UserCreate, db: Session) -> dict:
    try:
        role = _validate_role_and_person(db, user)
        payload = _build_payload(user, role)

        duplicate = user_model.find_duplicate(
            db,
            payload["email"],
            payload["username"],
        )

        if duplicate == "email":
            raise HTTPException(status_code=409, detail="Email already exists")

        if duplicate == "username":
            raise HTTPException(
                status_code=409,
                detail="Username already exists",
            )

        created = user_model.insert_user(db, payload)

        if created is None:
            raise HTTPException(
                status_code=502,
                detail="User could not be created",
            )

        db.commit()
        return created

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_error(exc) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while creating user")
        raise HTTPException(
            status_code=503,
            detail="User service unavailable",
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error while creating user")
        raise HTTPException(
            status_code=500,
            detail="Unable to create user",
        ) from exc


def update_user(user_id: int, user: UserCreate, db: Session) -> dict:
    try:
        existing = user_model.get_user_by_id(db, user_id)

        if existing is None:
            raise HTTPException(status_code=404, detail="User not found")

        role = _validate_role_and_person(db, user)
        payload = _build_payload(user, role)

        duplicate = user_model.find_duplicate(
            db,
            payload["email"],
            payload["username"],
            exclude_user_id=user_id,
        )

        if duplicate == "email":
            raise HTTPException(status_code=409, detail="Email already exists")

        if duplicate == "username":
            raise HTTPException(
                status_code=409,
                detail="Username already exists",
            )

        updated = user_model.update_user_record(
            db,
            user_id,
            payload,
        )

        if updated is None:
            raise HTTPException(status_code=404, detail="User not found")

        db.commit()
        return updated

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_error(exc) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while updating user %s", user_id)
        raise HTTPException(
            status_code=503,
            detail="User service unavailable",
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error while updating user %s", user_id)
        raise HTTPException(
            status_code=500,
            detail="Unable to update user",
        ) from exc


def delete_user(user_id: int, db: Session) -> dict:
    try:
        deleted = user_model.delete_user_record(db, user_id)

        if deleted is None:
            raise HTTPException(status_code=404, detail="User not found")

        db.commit()

        return {
            "success": True,
            "message": "User deleted successfully",
            "user": deleted,
        }

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.exception("Integrity error while deleting user %s", user_id)
        raise HTTPException(
            status_code=409,
            detail="User cannot be deleted because related records exist",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while deleting user %s", user_id)
        raise HTTPException(
            status_code=503,
            detail="User service unavailable",
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error while deleting user %s", user_id)
        raise HTTPException(
            status_code=500,
            detail="Unable to delete user",
        ) from exc
