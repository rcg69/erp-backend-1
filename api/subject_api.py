from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.subject_schema import (
    SubjectCreate,
    SubjectResponse,
    SubjectUpdate,
)
from services import subject_service


router = APIRouter(
    prefix="/api/subjects",
    tags=["Subjects"],
)


@router.post(
    "",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_subject(
    subject_data: SubjectCreate,
    db: Session = Depends(get_db),
):
    return subject_service.create_subject(
        subject_data,
        db,
    )


@router.get(
    "",
    response_model=list[SubjectResponse],
)
def get_subjects(
    db: Session = Depends(get_db),
):
    return subject_service.get_subjects(db)


@router.get(
    "/{subject_id}",
    response_model=SubjectResponse,
)
def get_subject(
    subject_id: int,
    db: Session = Depends(get_db),
):
    return subject_service.get_subject(
        subject_id,
        db,
    )


@router.put(
    "/{subject_id}",
    response_model=SubjectResponse,
)
def update_subject(
    subject_id: int,
    subject_data: SubjectUpdate,
    db: Session = Depends(get_db),
):
    return subject_service.update_subject(
        subject_id,
        subject_data,
        db,
    )


@router.delete("/{subject_id}")
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
):
    return subject_service.delete_subject(
        subject_id,
        db,
    )