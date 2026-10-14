from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.user_details_schema import UserDetailsResponse, UserDetailsUpdate
from security.auth import get_current_user, require_admin
from services import user_details_service


router = APIRouter(
    prefix="/api/user-details",
    tags=["User Details"],
)


@router.get("/me", response_model=UserDetailsResponse)
def get_my_user_details(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_details_service.get_user_details(current_user["id"], db)


@router.patch("/me", response_model=UserDetailsResponse)
def update_my_user_details(
    details: UserDetailsUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return user_details_service.update_user_details(
        current_user["id"],
        details,
        db,
    )


@router.get("/{user_id}", response_model=UserDetailsResponse)
def get_user_details(
    user_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return user_details_service.get_user_details(user_id, db)


@router.patch("/{user_id}", response_model=UserDetailsResponse)
def update_user_details(
    user_id: int,
    details: UserDetailsUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return user_details_service.update_user_details(user_id, details, db)
