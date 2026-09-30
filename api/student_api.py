from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.student_schema import StudentCreate, StudentUpdate
from security.auth import get_current_user, require_admin
from services import student_service


router = APIRouter(
    prefix="/api/students",
    tags=["Students/Staff"],
)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_student(
    student: StudentCreate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return student_service.create_student(
        student,
        db,
    )


@router.get("")
def get_students(
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return student_service.get_students(db)


@router.get("/{student_id}")
def get_student(
    student_id: int,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return student_service.get_student(
        student_id,
        db,
    )


@router.put("/{student_id}")
def update_student(
    student_id: int,
    student: StudentUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return student_service.update_student(
        student_id,
        student,
        db,
    )


@router.delete("/{student_id}")
def delete_student(
    student_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return student_service.delete_student(
        student_id,
        db,
    )