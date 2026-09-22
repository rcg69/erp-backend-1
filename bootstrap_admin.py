import getpass
import sys

from sqlalchemy import text

from database import SessionLocal
from service.password_service import hash_password


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python bootstrap_admin.py EMAIL USERNAME")

    email, username = sys.argv[1:]
    password = getpass.getpass("Initial admin password: ")
    db = SessionLocal()
    try:
        role = db.execute(
            text("SELECT role_id FROM roles WHERE lower(role_name) = 'admin' LIMIT 1")
        ).mappings().first()
        if not role:
            raise SystemExit("The admin role must exist before bootstrapping")

        existing_admin = db.execute(
            text("SELECT id FROM users WHERE role_id = :role_id LIMIT 1"),
            {"role_id": role["id"]},
        ).first()
        if existing_admin:
            raise SystemExit("An admin already exists; refusing to create another bootstrap admin")

        db.execute(
            text(
                """
                INSERT INTO users (email, username, password_hash, role_id, is_active)
                VALUES (:email, :username, :password_hash, :role_id, TRUE)
                """
            ),
            {
                "email": email.strip().lower(),
                "username": username.strip(),
                "password_hash": hash_password(password),
                "role_id": role["role_id"],
            },
        )
        db.commit()
        print("Admin user created successfully")
    finally:
        db.close()


if __name__ == "__main__":
    main()
