from fastapi import APIRouter, Depends, HTTPException, status

from database import supabase_admin
from schemas.user_schema import UserCreate, UserResponse
from security.auth import require_admin
from service.password_service import hash_password


router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
)


@router.get("", response_model=list[UserResponse])
def get_users(_current_admin=Depends(require_admin)):
    try:
        response = (
            supabase_admin.table("users")
            .select("id, email, username, person_id, role_id, is_active")
            .order("id")
            .execute()
        )
        return response.data or []
    except Exception as exc:
        print("[USER LIST] Failed:", type(exc).__name__, str(exc))
        raise HTTPException(status_code=503, detail="User service unavailable") from exc


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, current_admin=Depends(require_admin)):
    role_name = user.role.strip().lower()
    email = str(user.email)
    print("[USER CREATE] Request received")
    print("[USER CREATE] Admin user:", current_admin.get("id"), "role_id:", current_admin.get("role_id"))
    print("[USER CREATE] Email:", email, "username:", user.username, "role:", role_name)

    try:
        print("[USER CREATE] Looking up role")
        role_response = (
            supabase_admin.table("roles")
            .select("id, name")
            .eq("name", role_name)
            .maybe_single()
            .execute()
        )
        print("[USER CREATE] Role lookup result:", role_response.data)
        if not role_response.data:
            raise HTTPException(status_code=422, detail="Invalid role")

        print("[USER CREATE] Checking email uniqueness")
        existing_email = (
            supabase_admin.table("users")
            .select("id")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        print("[USER CREATE] Existing email match:", bool(existing_email.data))
        if existing_email.data:
            raise HTTPException(status_code=409, detail="Email or username already exists")

        print("[USER CREATE] Checking username uniqueness")
        existing_username = (
            supabase_admin.table("users")
            .select("id")
            .eq("username", user.username)
            .limit(1)
            .execute()
        )
        print("[USER CREATE] Existing username match:", bool(existing_username.data))
        if existing_username.data:
            raise HTTPException(status_code=409, detail="Email or username already exists")

        print("[USER CREATE] Hashing password")
        password_hash = hash_password(user.password)
        print("[USER CREATE] Password hash created; length:", len(password_hash))
        print("[USER CREATE] Inserting user profile")
        response = (
            supabase_admin.table("users")
            .insert({
                "email": email,
                "username": user.username,
                "password_hash": password_hash,
                "role_id": role_response.data["id"],
                "is_active": True,
                **({"person_id": user.person_id} if user.person_id is not None else {}),
            })
            .execute()
        )
        print("[USER CREATE] Insert response rows:", len(response.data or []))
        if response.data:
            print("[USER CREATE] Created profile fields:", sorted(response.data[0].keys()))
        if not response.data:
            raise HTTPException(status_code=502, detail="User could not be created")
        print("[USER CREATE] User created successfully; id:", response.data[0].get("id"))
        return response.data[0]

    except HTTPException:
        raise

    except Exception as exc:
        message = str(exc).lower()
        print("[USER CREATE] Failed at database/service boundary:", type(exc).__name__, str(exc))
        if "does not exist" in message or getattr(exc, "code", None) == "42703":
            raise HTTPException(
                status_code=503,
                detail="Database schema is outdated; run supabase_schema.sql before creating users",
            ) from exc
        if "duplicate" in message or "already exists" in message:
            raise HTTPException(status_code=409, detail="Email or username already exists") from exc
        raise HTTPException(status_code=503, detail="User service unavailable") from exc