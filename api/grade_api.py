from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db

from schemas.grade_schema import (
    GradeCreate,
    GradeResponse,
    GradeUpdate,
)

from services import grade_service


router = APIRouter(
    prefix="/api/grades",
    tags=["Grades"]
)


@router.post(
    "",
    response_model=GradeResponse,
    status_code=status.HTTP_201_CREATED
)
def create_grade(
    grade_data: GradeCreate,
    db: Session = Depends(get_db)
):
    return grade_service.create_grade(grade_data, db)


@router.get(
    "",
    response_model=list[GradeResponse]
)
def get_grades(
    db: Session = Depends(get_db)
):
    return grade_service.get_grades(db)


@router.get(
    "/{grade_id}",
    response_model=GradeResponse
)
def get_grade(
    grade_id: int,
    db: Session = Depends(get_db)
):
    return grade_service.get_grade(grade_id, db)


@router.put(
    "/{grade_id}",
    response_model=GradeResponse
)
def update_grade(
    grade_id: int,
    grade_data: GradeUpdate,
    db: Session = Depends(get_db)
):
    return grade_service.update_grade(
        grade_id,
        grade_data,
        db
    )


@router.delete("/{grade_id}")
def delete_grade(
    grade_id: int,
    db: Session = Depends(get_db)
):
    return grade_service.delete_grade(
        grade_id,
        db
    )