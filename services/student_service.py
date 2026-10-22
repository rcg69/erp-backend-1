
import logging

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from models import student_model
from schemas.student_schema import StudentCreate, StudentUpdate


logger = logging.getLogger(__name__)


def create_student(
    student: StudentCreate,
    db: Session,
) -> dict:
    try:
        payload = student.model_dump()

        # Roll numbers must be unique within the same grade and section.
        duplicate = student_model.find_duplicate_roll_number(
            db,
            roll_number=payload["roll_number"],
            grade=payload["grade"],
            section=payload["section"],
        )

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="This roll number already exists in this grade and section",
            )

        created = student_model.insert_student(db, payload)

        if created is None:
            raise HTTPException(
                status_code=500,
                detail="Student could not be created",
            )

        db.commit()

        return {
            "success": True,
            "message": "Student created successfully",
            "student": created,
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "Student creation violated a database constraint",
            exc_info=True,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Student could not be created because of a data conflict. "
                "Check the roll number, grade, and section."
            ),
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while creating student")
        raise HTTPException(
            status_code=503,
            detail="Student service temporarily unavailable",
        ) from exc


def get_students(db: Session) -> dict:
    try:
        students = student_model.get_all_students(db)

        return {
            "success": True,
            "count": len(students),
            "students": students,
        }

    except SQLAlchemyError as exc:
        logger.exception("Database error while listing students")
        raise HTTPException(
            status_code=503,
            detail="Student service temporarily unavailable",
        ) from exc


def get_student(
    student_id: int,
    db: Session,
) -> dict:
    try:
        student = student_model.get_student_by_id(db, student_id)

        if student is None:
            raise HTTPException(
                status_code=404,
                detail="Student not found",
            )

        return {
            "success": True,
            "student": student,
        }

    except HTTPException:
        raise

    except SQLAlchemyError as exc:
        logger.exception("Database error while retrieving student")
        raise HTTPException(
            status_code=503,
            detail="Student service temporarily unavailable",
        ) from exc


def update_student(
    student_id: int,
    student: StudentUpdate,
    db: Session,
) -> dict:
    # Update only fields explicitly supplied by the client.
    payload = student.model_dump(exclude_unset=True)

    if not payload:
        raise HTTPException(
            status_code=400,
            detail="No student fields were provided for update",
        )

    # Required fields cannot be set to null.
    for field in ("name", "roll_number", "status"):
        if field in payload and payload[field] is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot be null",
            )

    try:
        # Check existence before checking duplicate roll numbers.
        existing = student_model.get_student_by_id(db, student_id)

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="Student not found",
            )

        # Use existing values for fields omitted from the update request.
        roll_number = payload.get(
            "roll_number",
            existing["roll_number"],
        )
        grade = payload.get("grade", existing["grade"])
        section = payload.get("section", existing["section"])

        # Exclude this student so unchanged values are allowed.
        duplicate = student_model.find_duplicate_roll_number(
            db,
            roll_number=roll_number,
            grade=grade,
            section=section,
            exclude_student_id=student_id,
        )

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This roll number already exists "
                    "in this grade and section"
                ),
            )

        updated = student_model.update_student_record(
            db,
            student_id,
            payload,
        )

        if updated is None:
            raise HTTPException(
                status_code=400,
                detail="No valid student fields were provided for update",
            )

        db.commit()

        return {
            "success": True,
            "message": "Student updated successfully",
            "student": updated,
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "Student update violated a database constraint",
            exc_info=True,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Student could not be updated because of a data conflict. "
                "Check the roll number, grade, and section."
            ),
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while updating student")
        raise HTTPException(
            status_code=503,
            detail="Student service temporarily unavailable",
        ) from exc


def delete_student(
    student_id: int,
    db: Session,
) -> dict:
    try:
        deleted = student_model.delete_student_record(
            db,
            student_id,
        )

        if deleted is None:
            raise HTTPException(
                status_code=404,
                detail="Student not found",
            )

        db.commit()

        return {
            "success": True,
            "message": "Student deleted successfully",
            "student": deleted,
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "Student deletion was blocked by a database constraint",
            exc_info=True,
        )
        raise HTTPException(
            status_code=409,
            detail="Student cannot be deleted because related records exist",
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while deleting student")
        raise HTTPException(
            status_code=503,
            detail="Student service temporarily unavailable",
        ) from exc
