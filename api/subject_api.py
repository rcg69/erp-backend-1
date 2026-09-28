from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from schemas.subject_schema import (
    SubjectCreate,
    SubjectResponse,
    SubjectUpdate,
)

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
    try:
        record = db.execute(
            text(
                """
                INSERT INTO subjects (
                    code,
                    name,
                    description,
                    status
                )
                VALUES (
                    :code,
                    :name,
                    :description,
                    :status
                )
                RETURNING
                    id,
                    code,
                    name,
                    description,
                    status,
                    created_at
                """
            ),
            {
                "code": subject_data.code,
                "name": subject_data.name,
                "description": subject_data.description,
                "status": subject_data.status or "active",
            },
        ).mappings().first()

        db.commit()

        return dict(record)

    except Exception as exc:
        db.rollback()

        if "unique" in str(exc).lower():
            raise HTTPException(
                status_code=409,
                detail="Subject code or name already exists",
            ) from exc

        raise HTTPException(
            status_code=503,
            detail="Subject service unavailable",
        ) from exc


@router.get(
    "",
    response_model=list[SubjectResponse],
)
def get_subjects(
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    code,
                    name,
                    description,
                    status,
                    created_at
                FROM subjects
                ORDER BY name
                """
            )
        ).mappings().all()

        return [dict(row) for row in rows]

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Subject service unavailable",
        ) from exc


@router.get(
    "/{subject_id}",
    response_model=SubjectResponse,
)
def get_subject(
    subject_id: int,
    db: Session = Depends(get_db),
):
    row = db.execute(
        text(
            """
            SELECT
                id,
                code,
                name,
                description,
                status,
                created_at
            FROM subjects
            WHERE id = :subject_id
            """
        ),
        {
            "subject_id": subject_id,
        },
    ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Subject not found",
        )

    return dict(row)


@router.put(
    "/{subject_id}",
    response_model=SubjectResponse,
)
def update_subject(
    subject_id: int,
    subject_data: SubjectUpdate,
    db: Session = Depends(get_db),
):
    payload = {
        "code": subject_data.code,
        "name": subject_data.name,
        "description": subject_data.description,
        "status": subject_data.status,
        "subject_id": subject_id,
    }

    set_clauses = []

    for field_name in [
        "code",
        "name",
        "description",
        "status",
    ]:
        if payload[field_name] is not None:
            set_clauses.append(
                f"{field_name} = :{field_name}"
            )

    if not set_clauses:
        raise HTTPException(
            status_code=400,
            detail="No subject fields were provided for update",
        )

    try:
        row = db.execute(
            text(
                f"""
                UPDATE subjects
                SET {', '.join(set_clauses)}
                WHERE id = :subject_id
                RETURNING
                    id,
                    code,
                    name,
                    description,
                    status,
                    created_at
                """
            ),
            payload,
        ).mappings().first()

        db.commit()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Subject not found",
            )

        return dict(row)

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        if "unique" in str(exc).lower():
            raise HTTPException(
                status_code=409,
                detail="Subject code or name already exists",
            ) from exc

        raise HTTPException(
            status_code=503,
            detail="Subject service unavailable",
        ) from exc


@router.delete("/{subject_id}")
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                """
                DELETE FROM subjects
                WHERE id = :subject_id
                RETURNING
                    id,
                    code,
                    name,
                    description,
                    status,
                    created_at
                """
            ),
            {
                "subject_id": subject_id,
            },
        ).mappings().first()

        db.commit()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Subject not found",
            )

        return {
            "success": True,
            "message": "Subject deleted successfully",
            "subject": dict(row),
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail="Subject service unavailable",
        ) from exc