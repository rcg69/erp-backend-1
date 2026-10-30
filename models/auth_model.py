
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_user_by_email(
    db: Session,
    email: str,
) -> dict | None:
    result = db.execute(
        text(
            """
            SELECT
                id,
                username,
                email,
                person_id,
                role_id,
                is_active,
                password_hash
            FROM users
            WHERE email = :email
            LIMIT 1
            """
        ),
        {"email": email},
    ).mappings().first()

    return dict(result) if result else None


def get_user_by_id(
    db: Session,
    user_id: int,
) -> dict | None:
    result = db.execute(
        text(
            """
            SELECT
                id,
                username,
                email,
                person_id,
                role_id,
                is_active
            FROM users
            WHERE id = :user_id
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    ).mappings().first()

    return dict(result) if result else None


def create_password_reset_token(
    db: Session,
    user_id: int,
    token_hash: str,
    expires_at,
) -> None:
    db.execute(
        text("DELETE FROM password_reset_tokens WHERE user_id = :user_id AND used_at IS NULL"),
        {"user_id": user_id},
    )
    db.execute(
        text(
            """
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
            VALUES (:user_id, :token_hash, :expires_at)
            """
        ),
        {"user_id": user_id, "token_hash": token_hash, "expires_at": expires_at},
    )


def consume_password_reset_token(db: Session, token_hash: str) -> int | None:
    result = db.execute(
        text(
            """
            UPDATE password_reset_tokens
            SET used_at = CURRENT_TIMESTAMP
            WHERE token_hash = :token_hash
              AND used_at IS NULL
              AND expires_at > CURRENT_TIMESTAMP
            RETURNING user_id
            """
        ),
        {"token_hash": token_hash},
    ).first()
    return result[0] if result else None


def update_user_password(db: Session, user_id: int, password_hash: str) -> None:
    db.execute(
        text("UPDATE users SET password_hash = :password_hash WHERE id = :user_id"),
        {"password_hash": password_hash, "user_id": user_id},
    )
    db.execute(
        text("UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = :user_id AND revoked = FALSE"),
        {"user_id": user_id},
    )


def create_refresh_token_record(
    db: Session,
    user_id: int,
    token_hash: str,
    expires_at,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO refresh_tokens (
                user_id,
                token_hash,
                expires_at
            )
            VALUES (
                :user_id,
                :token_hash,
                :expires_at
            )
            """
        ),
        {
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at,
        },
    )


def get_valid_refresh_token(
    db: Session,
    token_hash: str,
    user_id: int,
) -> dict | None:
    result = db.execute(
        text(
            """
            SELECT id
            FROM refresh_tokens
            WHERE token_hash = :token_hash
              AND user_id = :user_id
              AND revoked = FALSE
              AND expires_at > CURRENT_TIMESTAMP
            LIMIT 1
            """
        ),
        {
            "token_hash": token_hash,
            "user_id": user_id,
        },
    ).mappings().first()

    return dict(result) if result else None


def revoke_refresh_token(
    db: Session,
    token_hash: str,
) -> None:
    db.execute(
        text(
            """
            UPDATE refresh_tokens
            SET revoked = TRUE
            WHERE token_hash = :token_hash
              AND revoked = FALSE
            """
        ),
        {"token_hash": token_hash},
    )


def revoke_refresh_token_by_id(
    db: Session,
    token_id: int,
) -> bool:
    result = db.execute(
        text(
            """
            UPDATE refresh_tokens
            SET revoked = TRUE
            WHERE id = :token_id
              AND revoked = FALSE
              AND expires_at > CURRENT_TIMESTAMP
            RETURNING id
            """
        ),
        {"token_id": token_id},
    ).first()

    return result is not None
