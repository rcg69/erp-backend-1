import getpass
import sys

from database import supabase_admin
from service.password_service import hash_password


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python migrate_legacy_user.py EMAIL")

    email = sys.argv[1]
    password = getpass.getpass("New password: ")
    response = (
        supabase_admin.table("users")
        .select("id, email")
        .eq("email", email)
        .maybe_single()
        .execute()
    )
    if not response.data:
        raise SystemExit("User not found")

    supabase_admin.table("users").update({
        "password_hash": hash_password(password),
        "is_active": True,
    }).eq("id", response.data["id"]).execute()
    print("User password migrated successfully")


if __name__ == "__main__":
    main()
