from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from security.auth import get_current_user
from database import get_db

from schemas.user_schema import UserCreate, UserResponse
from services.password_service import hash_password


router = APIRouter(
    prefix="/api/users",
    tags=["Users"]
)

USER_COLUMNS = "id, email, username, person_id, role_id, is_active"


def _duplicate_error(exc: Exception) -> HTTPException:
    message = str(exc).lower()

    if "email" in message:
        return HTTPException(
            status_code=409,
            detail="Email already exists"
        )

    if "username" in message:
        return HTTPException(
            status_code=409,
            detail="Username already exists"
        )

    return HTTPException(
        status_code=409,
        detail="Email or username already exists"
    )


def _user_payload(user: UserCreate, role_id: int) -> dict:
    return {
        "email": str(user.email).strip().lower(),
        "username": user.username.strip(),
        "password_hash": hash_password(user.password),
        "role_id": role_id,
        "person_id": user.person_id,
    }


@router.get("", response_model=list[UserResponse])
def get_users(
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        users = db.execute(
            text(
                f"""
                SELECT {USER_COLUMNS}
                FROM users
                ORDER BY id
                """
            )
        ).mappings().all()

        return [dict(user) for user in users]

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="User service unavailable"
        ) from exc


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user = db.execute(
            text(
                f"""
                SELECT {USER_COLUMNS}
                FROM users
                WHERE id = :user_id
                """
            ),
            {"user_id": user_id},
        ).mappings().first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        return dict(user)

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="User service unavailable"
        ) from exc


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def create_user(
    user: UserCreate,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:

        # ---------------------------------------------------------
        # 1. Find the role
        # ---------------------------------------------------------

        role_name = user.role.strip().lower()

        role = db.execute(
            text(
                """
                SELECT role_id
                FROM roles
                WHERE lower(role_name) = :role_name
                LIMIT 1
                """
            ),
            {"role_name": role_name},
        ).mappings().first()

        if not role:
            raise HTTPException(
                status_code=422,
                detail="Invalid role"
            )

        # ---------------------------------------------------------
        # 2. Check person_id according to the role
        # ---------------------------------------------------------

        if role_name == "student":

            person = db.execute(
                text(
                    """
                    SELECT id
                    FROM students
                    WHERE id = :person_id
                    LIMIT 1
                    """
                ),
                {"person_id": user.person_id},
            ).first()

            if not person:
                raise HTTPException(
                    status_code=422,
                    detail="person_id must reference an existing student"
                )

        elif role_name == "staff":

            person = db.execute(
                text(
                    """
                    SELECT id
                    FROM staff
                    WHERE id = :person_id
                    LIMIT 1
                    """
                ),
                {"person_id": user.person_id},
            ).first()

            if not person:
                raise HTTPException(
                    status_code=422,
                    detail="person_id must reference an existing staff member"
                )

        elif role_name == "admin":

            # Admin does not require a student/staff person_id.
            pass

        else:

            raise HTTPException(
                status_code=422,
                detail="Invalid role"
            )

        # ---------------------------------------------------------
        # 3. Prepare user data
        # ---------------------------------------------------------

        payload = _user_payload(
            user,
            role["role_id"]
        )

        # ---------------------------------------------------------
        # 4. Check duplicate email/username
        # ---------------------------------------------------------

        exists = db.execute(
            text(
                """
                SELECT 1
                FROM users
                WHERE email = :email
                   OR username = :username
                LIMIT 1
                """
            ),
            {
                "email": payload["email"],
                "username": payload["username"],
            },
        ).first()

        if exists:
            raise HTTPException(
                status_code=409,
                detail="Email or username already exists"
            )

        # ---------------------------------------------------------
        # 5. Create user
        # ---------------------------------------------------------

        created = db.execute(
            text(
                f"""
                INSERT INTO users
                (
                    email,
                    username,
                    password_hash,
                    role_id,
                    person_id,
                    is_active
                )
                VALUES
                (
                    :email,
                    :username,
                    :password_hash,
                    :role_id,
                    :person_id,
                    TRUE
                )
                RETURNING {USER_COLUMNS}
                """
            ),
            payload,
        ).mappings().first()

        db.commit()

        if not created:
            raise HTTPException(
                status_code=502,
                detail="User could not be created"
            )

        return dict(created)

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_error(exc) from exc

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="User service unavailable"
        ) from exc


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user: UserCreate,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:

        # ---------------------------------------------------------
        # 1. Check existing user
        # ---------------------------------------------------------

        existing = db.execute(
            text(
                """
                SELECT id
                FROM users
                WHERE id = :user_id
                """
            ),
            {"user_id": user_id},
        ).first()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        # ---------------------------------------------------------
        # 2. Find role
        # ---------------------------------------------------------

        role_name = user.role.strip().lower()

        role = db.execute(
            text(
                """
                SELECT role_id
                FROM roles
                WHERE lower(role_name) = :role_name
                LIMIT 1
                """
            ),
            {"role_name": role_name},
        ).mappings().first()

        if not role:
            raise HTTPException(
                status_code=422,
                detail="Invalid role"
            )

        # ---------------------------------------------------------
        # 3. Check person_id according to role
        # ---------------------------------------------------------

        if role_name == "student":

            person = db.execute(
                text(
                    """
                    SELECT id
                    FROM students
                    WHERE id = :person_id
                    LIMIT 1
                    """
                ),
                {"person_id": user.person_id},
            ).first()

            if not person:
                raise HTTPException(
                    status_code=422,
                    detail="person_id must reference an existing student"
                )

        elif role_name == "staff":

            person = db.execute(
                text(
                    """
                    SELECT id
                    FROM staff
                    WHERE id = :person_id
                    LIMIT 1
                    """
                ),
                {"person_id": user.person_id},
            ).first()

            if not person:
                raise HTTPException(
                    status_code=422,
                    detail="person_id must reference an existing staff member"
                )

        elif role_name == "admin":

            # Admin does not require a student/staff person_id.
            pass

        else:

            raise HTTPException(
                status_code=422,
                detail="Invalid role"
            )

        # ---------------------------------------------------------
        # 4. Prepare payload
        # ---------------------------------------------------------

        payload = _user_payload(
            user,
            role["role_id"]
        )

        # ---------------------------------------------------------
        # 5. Check duplicate email/username
        # ---------------------------------------------------------

        duplicate = db.execute(
            text(
                """
                SELECT 1
                FROM users
                WHERE (email = :email OR username = :username)
                  AND id != :user_id
                LIMIT 1
                """
            ),
            {
                "email": payload["email"],
                "username": payload["username"],
                "user_id": user_id,
            },
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="Email or username already exists"
            )

        # ---------------------------------------------------------
        # 6. Update user
        # ---------------------------------------------------------

        updated = db.execute(
            text(
                f"""
                UPDATE users
                SET
                    email = :email,
                    username = :username,
                    password_hash = :password_hash,
                    role_id = :role_id,
                    person_id = :person_id
                WHERE id = :user_id
                RETURNING {USER_COLUMNS}
                """
            ),
            {
                **payload,
                "user_id": user_id,
            },
        ).mappings().first()

        db.commit()

        if not updated:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        return dict(updated)

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_error(exc) from exc

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="User service unavailable"
        ) from exc


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:

        # ---------------------------------------------------------
        # 1. Delete user
        # ---------------------------------------------------------

        deleted = db.execute(
            text(
                f"""
                DELETE FROM users
                WHERE id = :user_id
                RETURNING {USER_COLUMNS}
                """
            ),
            {"user_id": user_id},
        ).mappings().first()

        db.commit()

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        return {
            "success": True,
            "message": "User deleted successfully",
            "user": dict(deleted),
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="User service unavailable"
        ) from exc