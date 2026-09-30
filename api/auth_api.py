from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

from database import get_db

from schemas.auth_schema import (
    LoginRequest,
    LoginResponse,
    RefreshResponse,
)

from schemas.user_schema import UserResponse

from security.auth import get_current_user

from services import auth_service


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.get(
    "/me",
    response_model=UserResponse
)
def get_me(
    current_user=Depends(get_current_user)
):
    return current_user


@router.post(
    "/login",
    response_model=LoginResponse
)
def login(
    credentials: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    return auth_service.login(
        credentials,
        response,
        db
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse
)
def refresh_access_token(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=auth_service.REFRESH_COOKIE_NAME
    ),
    db: Session = Depends(get_db),
):
    return auth_service.refresh_access_token(
        response,
        refresh_token,
        db
    )


@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str | None = Cookie(
        default=None,
        alias=auth_service.REFRESH_COOKIE_NAME
    ),
    db: Session = Depends(get_db),
):
    return auth_service.logout(
        response,
        refresh_token,
        db
    )