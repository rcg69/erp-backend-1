from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db

from schemas.user_schema import UserCreate, UserResponse

from security.auth import get_current_user

from services import user_create_service


router = APIRouter(
    prefix="/api/users",
    tags=["Users"]
)


@router.get("", response_model=list[UserResponse])
def get_users(
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_create_service.get_users(db)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_create_service.get_user(user_id, db)


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
    return user_create_service.create_user(user, db)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user: UserCreate,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_create_service.update_user(user_id, user, db)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_create_service.delete_user(user_id, db)