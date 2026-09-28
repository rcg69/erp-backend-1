import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db

from schemas.attendance_schema import (
    AttendanceBulkCreate,
    AttendanceCreate,
    AttendanceResponse,
    AttendanceUpdate,
)


router = APIRouter(
    prefix="/api/attendance",
    tags=["Attendance"]
)


# =========================================================
# HELPERS
# =========================================================

def _normalize_grade(value):
    """'10', '10th', '10th Class' -> '10'. Non-numeric grades compare as text."""
    if value is None:
        return None

    text_value = str(value).strip().lower()

    if not text_value:
        return None

    match = re.search(r"\d+", text_value)

    return match.group(0) if match else text_value


def _get_session_context(db: Session, session_id: int):
    """Return the section (and class) a class session belongs to."""
    row = db.execute(
        text(
            """
            SELECT
                cs.id,
                sec.section AS section,
                g.grade AS grade
            FROM class_sessions cs
            JOIN timetables t ON t.id = cs.timetable_id
            JOIN sections sec ON sec.id = t.section_id
            LEFT JOIN grades g ON g.id = t.grade_id
            WHERE cs.id = :session_id
            """
        ),
        {
            "session_id": session_id,
        },
    ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found",
        )

    return row


def _student_in_session_class(student, context) -> bool:
    student_section = (student["section"] or "").strip().lower()

    if student_section != (context["section"] or "").strip().lower():
        return False

    # Only compare the class when both sides have one.
    session_grade = _normalize_grade(context["grade"])
    student_grade = _normalize_grade(student["grade"])

    if session_grade and student_grade and session_grade != student_grade:
        return False

    return True


def _validate_students_for_session(
    db: Session,
    context,
    student_ids: list[int],
):
    """
    One query for all students. Raises 404 if any student does not exist
    and 400 if any student is not in the session's section.
    """
    rows = db.execute(
        text(
            """
            SELECT id, section, grade
            FROM students
            WHERE id = ANY(:student_ids)
            """
        ),
        {
            "student_ids": student_ids,
        },
    ).mappings().all()

    found = {row["id"]: row for row in rows}

    missing = sorted(set(student_ids) - set(found))

    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found: "
            + ", ".join(str(student_id) for student_id in missing),
        )

    outside = [
        student_id
        for student_id in student_ids
        if not _student_in_session_class(found[student_id], context)
    ]

    if outside:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student(s) not in this session's section: "
            + ", ".join(str(student_id) for student_id in outside),
        )



# =========================================================
# CREATE ATTENDANCE
# =========================================================

@router.post(
    "",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_attendance(
    attendance_data: AttendanceCreate,
    db: Session = Depends(get_db),
):
    # Verify session exists and load its section
    context = _get_session_context(db, attendance_data.session_id)

    # Verify student exists and belongs to the session's section
    _validate_students_for_session(
        db,
        context,
        [attendance_data.student_id],
    )

    try:
        row = db.execute(
            text(
                """
                INSERT INTO attendance (
                    session_id,
                    student_id,
                    status,
                    remarks
                )
                VALUES (
                    :session_id,
                    :student_id,
                    :status,
                    :remarks
                )
                RETURNING
                    id,
                    session_id,
                    student_id,
                    status,
                    remarks
                """
            ),
            {
                "session_id": attendance_data.session_id,
                "student_id": attendance_data.student_id,
                "status": attendance_data.status,
                "remarks": attendance_data.remarks,
            },
        ).mappings().first()

        db.commit()

        return dict(row)

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance already exists for this student and session",
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attendance service unavailable",
        ) from exc


# =========================================================
# GET ATTENDANCE
# =========================================================

@router.get(
    "",
    response_model=list[AttendanceResponse],
)
def get_attendance(
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    session_id,
                    student_id,
                    status,
                    remarks
                FROM attendance
                ORDER BY id DESC
                """
            )
        ).mappings().all()

        return [dict(row) for row in rows]

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attendance service unavailable",
        ) from exc


# =========================================================
# GET SINGLE ATTENDANCE
# =========================================================

@router.get(
    "/{attendance_id}",
    response_model=AttendanceResponse,
)
def get_attendance_record(
    attendance_id: int,
    db: Session = Depends(get_db),
):
    row = db.execute(
        text(
            """
            SELECT
                id,
                session_id,
                student_id,
                status,
                remarks
            FROM attendance
            WHERE id = :attendance_id
            """
        ),
        {
            "attendance_id": attendance_id,
        },
    ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found",
        )

    return dict(row)


# =========================================================
# UPDATE ATTENDANCE
# =========================================================

@router.put(
    "/{attendance_id}",
    response_model=AttendanceResponse,
)
def update_attendance(
    attendance_id: int,
    attendance_data: AttendanceUpdate,
    db: Session = Depends(get_db),
):
    payload = {
        "status": attendance_data.status,
        "remarks": attendance_data.remarks,
        "attendance_id": attendance_id,
    }

    set_clauses = []

    for field_name in [
        "status",
        "remarks",
    ]:
        if payload[field_name] is not None:
            set_clauses.append(
                f"{field_name} = :{field_name}"
            )

    if not set_clauses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No attendance fields were provided for update",
        )

    try:
        row = db.execute(
            text(
                f"""
                UPDATE attendance
                SET {', '.join(set_clauses)}
                WHERE id = :attendance_id
                RETURNING
                    id,
                    session_id,
                    student_id,
                    status,
                    remarks
                """
            ),
            payload,
        ).mappings().first()

        if not row:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attendance record not found",
            )

        db.commit()

        return dict(row)

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attendance service unavailable",
        ) from exc


# =========================================================
# DELETE ATTENDANCE
# =========================================================

@router.delete(
    "/{attendance_id}",
)
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                """
                DELETE FROM attendance
                WHERE id = :attendance_id
                RETURNING id
                """
            ),
            {
                "attendance_id": attendance_id,
            },
        ).mappings().first()

        if not row:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attendance record not found",
            )

        db.commit()

        return {
            "success": True,
            "message": "Attendance deleted successfully",
            "id": row["id"],
        }

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attendance service unavailable",
        ) from exc


# =========================================================
# BULK ATTENDANCE
# =========================================================

@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
)
def create_bulk_attendance(
    attendance_data: AttendanceBulkCreate,
    db: Session = Depends(get_db),
):
    if not attendance_data.records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendance records cannot be empty",
        )

    student_ids = [record.student_id for record in attendance_data.records]

    duplicates = sorted(
        {
            student_id
            for student_id in student_ids
            if student_ids.count(student_id) > 1
        }
    )

    if duplicates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate student in attendance records: "
            + ", ".join(str(student_id) for student_id in duplicates),
        )

    # Verify session exists and load its section
    context = _get_session_context(db, attendance_data.session_id)

    # One query for every student instead of one per record
    _validate_students_for_session(db, context, student_ids)

    try:
        created_records = []

        for record in attendance_data.records:

            row = db.execute(
                text(
                    """
                    INSERT INTO attendance (
                        session_id,
                        student_id,
                        status,
                        remarks
                    )
                    VALUES (
                        :session_id,
                        :student_id,
                        :status,
                        :remarks
                    )
                    RETURNING
                        id,
                        session_id,
                        student_id,
                        status,
                        remarks
                    """
                ),
                {
                    "session_id": attendance_data.session_id,
                    "student_id": record.student_id,
                    "status": record.status,
                    "remarks": record.remarks,
                },
            ).mappings().first()

            created_records.append(dict(row))

        db.commit()

        return {
            "success": True,
            "message": "Attendance recorded successfully",
            "count": len(created_records),
            "records": created_records,
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance already exists for one or more students",
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attendance service unavailable",
        ) from exc