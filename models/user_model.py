
from sqlalchemy import text
from sqlalchemy.orm import Session


USER_COLUMNS = "id, email, username, person_id, role_id, is_active"


def get_all_users(db: Session) -> list[dict]:
    rows = db.execute(
        text(f"""
            SELECT {USER_COLUMNS}
            FROM users
            ORDER BY id
        """)
    ).mappings().all()

    return [dict(row) for row in rows]


def get_user_by_id(db: Session, user_id: int) -> dict | None:
    row = db.execute(
        text(f"""
            SELECT {USER_COLUMNS}
            FROM users
            WHERE id = :user_id
            LIMIT 1
        """),
        {"user_id": user_id},
    ).mappings().first()

    return dict(row) if row else None


def get_role(db: Session, role_name: str) -> dict | None:
    row = db.execute(
        text("""
            SELECT role_id, role_name
            FROM roles
            WHERE LOWER(role_name) = :role_name
            LIMIT 1
        """),
        {"role_name": role_name.strip().lower()},
    ).mappings().first()

    return dict(row) if row else None


def person_exists(
    db: Session,
    role_name: str,
    person_id: int | None,
) -> bool:
    role_name = role_name.strip().lower()

    # Admin accounts do not require a student/staff profile.
    if role_name == "admin":
        return True

    if person_id is None:
        return False

    if role_name == "student":
        query = """
            SELECT 1
            FROM students
            WHERE id = :person_id
            LIMIT 1
        """
    elif role_name in {"staff", "teacher"}:
        query = """
            SELECT 1
            FROM staff
            WHERE id = :person_id
            LIMIT 1
        """
    else:
        return False

    return (
        db.execute(text(query), {"person_id": person_id}).first()
        is not None
    )


def find_duplicate(
    db: Session,
    email: str,
    username: str,
    exclude_user_id: int | None = None,
) -> str | None:
    query = """
        SELECT
            CASE
                WHEN LOWER(email) = :email THEN 'email'
                WHEN LOWER(username) = LOWER(:username) THEN 'username'
            END AS duplicate_field
        FROM users
        WHERE (
            LOWER(email) = :email
            OR LOWER(username) = LOWER(:username)
        )
    """

    params = {
        "email": email.strip().lower(),
        "username": username.strip(),
    }

    if exclude_user_id is not None:
        query += " AND id != :exclude_user_id"
        params["exclude_user_id"] = exclude_user_id

    query += " LIMIT 1"

    row = db.execute(text(query), params).mappings().first()

    return row["duplicate_field"] if row else None


def insert_user(db: Session, payload: dict) -> dict | None:
    created = db.execute(
        text(f"""
            INSERT INTO users (
                email,
                username,
                password_hash,
                role_id,
                person_id,
                is_active
            )
            VALUES (
                :email,
                :username,
                :password_hash,
                :role_id,
                :person_id,
                TRUE
            )
            RETURNING {USER_COLUMNS}
        """),
        payload,
    ).mappings().first()

    if not created:
        return None

    user = dict(created)

    db.execute(
        text("""
            INSERT INTO user_details (user_id)
            VALUES (:user_id)
            ON CONFLICT (user_id) DO NOTHING
        """),
        {"user_id": user["id"]},
    )

    return user


def update_user_record(
    db: Session,
    user_id: int,
    payload: dict,
) -> dict | None:
    updated = db.execute(
        text(f"""
            UPDATE users
            SET
                email = :email,
                username = :username,
                password_hash = :password_hash,
                role_id = :role_id,
                person_id = :person_id
            WHERE id = :user_id
            RETURNING {USER_COLUMNS}
        """),
        {**payload, "user_id": user_id},
    ).mappings().first()

    return dict(updated) if updated else None


def delete_user_record(db: Session, user_id: int) -> dict | None:
    deleted = db.execute(
        text(f"""
            DELETE FROM users
            WHERE id = :user_id
            RETURNING {USER_COLUMNS}
        """),
        {"user_id": user_id},
    ).mappings().first()

    return dict(deleted) if deleted else None
