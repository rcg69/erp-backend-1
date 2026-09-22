import getpass
import sys

from sqlalchemy import text

from database import SessionLocal
from service.password_service import hash_password


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python migrate_legacy_user.py EMAIL")

    email = sys.argv[1].strip().lower()
    password = getpass.getpass("New password: ")
    db = SessionLocal()
    try:
        user = db.execute(
            text("SELECT id FROM users WHERE email = :email LIMIT 1"),
            {"email": email},
        ).mappings().first()
        if not user:
            raise SystemExit("User not found")

        db.execute(
            text(
                """
                UPDATE users
                SET password_hash = :password_hash, is_active = TRUE
                WHERE id = :user_id
                """
            ),
            {"password_hash": hash_password(password), "user_id": user["id"]},
        )
        db.commit()
        print("User password migrated successfully")
    finally:
        db.close()


if __name__ == "__main__":
    main()
