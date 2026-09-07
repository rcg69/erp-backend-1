import getpass
import sys

from database import supabase_admin
from service.password_service import hash_password


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python bootstrap_admin.py EMAIL USERNAME")

    email, username = sys.argv[1:]
    password = getpass.getpass("Initial admin password: ")
    role = (
        supabase_admin.table("roles")
        .select("id")
        .eq("name", "admin")
        .maybe_single()
        .execute()
    )
    if not role.data:
        raise SystemExit("The admin role must exist before bootstrapping")

    existing_admin = (
        supabase_admin.table("users")
        .select("id")
        .eq("role_id", role.data["id"])
        .limit(1)
        .execute()
    )
    if existing_admin.data:
        raise SystemExit("An admin already exists; refusing to create another bootstrap admin")

    supabase_admin.table("users").insert({
        "email": email,
        "username": username,
        "password_hash": hash_password(password),
        "role_id": role.data["id"],
        "is_active": True,
    }).execute()

    print("Initial admin created successfully")


if __name__ == "__main__":
    main()