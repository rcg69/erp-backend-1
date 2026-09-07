from fastapi import APIRouter, Depends, HTTPException, status

from database import supabase_admin
from schemas.auth_schema import LoginRequest, LoginResponse
from schemas.user_schema import UserResponse
from security.auth import get_current_user
from service.password_service import verify_password
from utils.jwt import create_access_token

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.get("/me", response_model=UserResponse)
def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest):
    email = str(credentials.email)
    print("[LOGIN] Attempting authentication for:", email)

    try:
        response = (
            supabase_admin.table("users")
            .select("id, username, email, person_id, role_id, is_active, password_hash")
            .eq("email", email)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        print("[LOGIN] User lookup failed:", type(exc).__name__, str(exc))
        if getattr(exc, "code", None) == "42703":
            raise HTTPException(
                status_code=503,
                detail="Database schema is outdated; run supabase_schema.sql before logging in",
            ) from exc
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from exc

    user = response.data
    if not user or not user.get("password_hash"):
        print("[LOGIN] Invalid credentials")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not verify_password(credentials.password, user["password_hash"]):
        print("[LOGIN] Invalid credentials")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.get("is_active", False):
        print("[LOGIN] Inactive user:", user["id"])
        raise HTTPException(status_code=403, detail="User account is inactive")

    try:
        access_token = create_access_token(
            user_id=user["id"],
            person_id=user.get("person_id"),
            role_id=user["role_id"],
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Authentication is not configured") from exc

    print("[LOGIN] Login successful for ERP user:", user["id"])

    return {
        "success": True,
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "person_id": user.get("person_id"),
            "role_id": user["role_id"],
            "is_active": user["is_active"],
        }
    }