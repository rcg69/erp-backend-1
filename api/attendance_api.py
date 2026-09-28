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
    # Verify session exists
    session = db.execute(
        text(
            """
            SELECT id
            FROM class_sessions
            WHERE id = :session_id
            """
        ),
        {
            "session_id": attendance_data.session_id,
        },
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found",
        )

    # Verify student exists
    student = db.execute(
        text(
            """
            SELECT id
            FROM students
            WHERE id = :student_id
            """
        ),
        {
            "student_id": attendance_data.student_id,
        },
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
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
    # Verify session
    session = db.execute(
        text(
            """
            SELECT id
            FROM class_sessions
            WHERE id = :session_id
            """
        ),
        {
            "session_id": attendance_data.session_id,
        },
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found",
        )

    if not attendance_data.records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendance records cannot be empty",
        )

    try:
        created_records = []

        for record in attendance_data.records:

            student = db.execute(
                text(
                    """
                    SELECT id
                    FROM students
                    WHERE id = :student_id
                    """
                ),
                {
                    "student_id": record.student_id,
                },
            ).first()

            if not student:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Student {record.student_id} not found",
                )

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