from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.staff_schema import StaffCreate, StaffResponse, StaffUpdate
from security.auth import get_current_user, require_admin
from services import staff_service


router = APIRouter(
    prefix="/api/staff",
    tags=["Staff"],
)


@router.post(
    "",
    response_model=StaffResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_staff(
    staff: StaffCreate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return staff_service.create_staff(
        staff,
        db,
    )


@router.get(
    "",
    response_model=list[StaffResponse],
)
def get_staff(
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return staff_service.get_staff(db)


@router.get(
    "/{staff_id}",
    response_model=StaffResponse,
)
def get_one_staff(
    staff_id: int,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return staff_service.get_one_staff(
        staff_id,
        db,
    )


@router.put(
    "/{staff_id}",
    response_model=StaffResponse,
)
def update_staff(
    staff_id: int,
    staff: StaffUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return staff_service.update_staff(
        staff_id,
        staff,
        db,
    )


@router.delete("/{staff_id}")
def delete_staff(
    staff_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return staff_service.delete_staff(
        staff_id,
        db,
    )