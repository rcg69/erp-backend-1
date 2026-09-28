from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db

from schemas.timetable_schema import (
    TimetableCreate,
    TimetableResponse,
    TimetableUpdate,
)

from schemas.class_session_schema import (
    ClassSessionCreate,
    ClassSessionResponse,
    ClassSessionUpdate,
)


router = APIRouter(
    prefix="/api/scheduling",
    tags=["Scheduling"]
)


# =========================================================
# TIMETABLES
# =========================================================

# ---------------------------------------------------------
# CREATE TIMETABLE
# ---------------------------------------------------------
@router.post(
    "/timetables",
    response_model=TimetableResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_timetable(
    timetable_data: TimetableCreate,
    db: Session = Depends(get_db),
):
    if timetable_data.start_time >= timetable_data.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time",
        )

    # Prevent overlapping timetable entries for the same section.
    conflict = db.execute(
        text(
            """
            SELECT id
            FROM timetables
            WHERE section_id = :section_id
              AND day_of_week = :day_of_week
              AND status = 'active'
              AND start_time < :end_time
              AND end_time > :start_time
            LIMIT 1
            """
        ),
        {
            "section_id": timetable_data.section_id,
            "day_of_week": timetable_data.day_of_week,
            "start_time": timetable_data.start_time,
            "end_time": timetable_data.end_time,
        },
    ).first()

    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This section already has a timetable entry during this time",
        )

    try:
        row = db.execute(
            text(
                """
                INSERT INTO timetables (
                    section_id,
                    subject_id,
                    staff_id,
                    day_of_week,
                    start_time,
                    end_time,
                    room,
                    status
                )
                VALUES (
                    :section_id,
                    :subject_id,
                    :staff_id,
                    :day_of_week,
                    :start_time,
                    :end_time,
                    :room,
                    :status
                )
                RETURNING
                    id,
                    section_id,
                    subject_id,
                    staff_id,
                    day_of_week,
                    start_time,
                    end_time,
                    room,
                    status
                """
            ),
            {
                "section_id": timetable_data.section_id,
                "subject_id": timetable_data.subject_id,
                "staff_id": timetable_data.staff_id,
                "day_of_week": timetable_data.day_of_week,
                "start_time": timetable_data.start_time,
                "end_time": timetable_data.end_time,
                "room": timetable_data.room,
                "status": timetable_data.status,
            },
        ).mappings().first()

        db.commit()

        return dict(row)

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid section, subject, or staff reference",
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling service unavailable",
        ) from exc


# ---------------------------------------------------------
# GET ALL TIMETABLES
# ---------------------------------------------------------
@router.get(
    "/timetables",
    response_model=list[TimetableResponse],
)
def get_timetables(
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    section_id,
                    subject_id,
                    staff_id,
                    day_of_week,
                    start_time,
                    end_time,
                    room,
                    status
                FROM timetables
                ORDER BY
                    section_id,
                    day_of_week,
                    start_time
                """
            )
        ).mappings().all()

        return [dict(row) for row in rows]

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling service unavailable",
        ) from exc


# ---------------------------------------------------------
# GET SINGLE TIMETABLE
# ---------------------------------------------------------
@router.get(
    "/timetables/{timetable_id}",
    response_model=TimetableResponse,
)
def get_timetable(
    timetable_id: int,
    db: Session = Depends(get_db),
):
    row = db.execute(
        text(
            """
            SELECT
                id,
                section_id,
                subject_id,
                staff_id,
                day_of_week,
                start_time,
                end_time,
                room,
                status
            FROM timetables
            WHERE id = :timetable_id
            """
        ),
        {
            "timetable_id": timetable_id,
        },
    ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable not found",
        )

    return dict(row)


# ---------------------------------------------------------
# UPDATE TIMETABLE
# ---------------------------------------------------------
@router.put(
    "/timetables/{timetable_id}",
    response_model=TimetableResponse,
)
def update_timetable(
    timetable_id: int,
    timetable_data: TimetableUpdate,
    db: Session = Depends(get_db),
):
    current = db.execute(
        text(
            """
            SELECT
                section_id,
                subject_id,
                staff_id,
                day_of_week,
                start_time,
                end_time,
                room,
                status
            FROM timetables
            WHERE id = :timetable_id
            """
        ),
        {
            "timetable_id": timetable_id,
        },
    ).mappings().first()

    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable not found",
        )

    values = {
        "section_id": (
            timetable_data.section_id
            if timetable_data.section_id is not None
            else current["section_id"]
        ),
        "subject_id": (
            timetable_data.subject_id
            if timetable_data.subject_id is not None
            else current["subject_id"]
        ),
        "staff_id": (
            timetable_data.staff_id
            if timetable_data.staff_id is not None
            else current["staff_id"]
        ),
        "day_of_week": (
            timetable_data.day_of_week
            if timetable_data.day_of_week is not None
            else current["day_of_week"]
        ),
        "start_time": (
            timetable_data.start_time
            if timetable_data.start_time is not None
            else current["start_time"]
        ),
        "end_time": (
            timetable_data.end_time
            if timetable_data.end_time is not None
            else current["end_time"]
        ),
        "room": (
            timetable_data.room
            if timetable_data.room is not None
            else current["room"]
        ),
        "status": (
            timetable_data.status
            if timetable_data.status is not None
            else current["status"]
        ),
        "timetable_id": timetable_id,
    }

    if values["start_time"] >= values["end_time"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time",
        )

    conflict = db.execute(
        text(
            """
            SELECT id
            FROM timetables
            WHERE section_id = :section_id
              AND day_of_week = :day_of_week
              AND status = 'active'
              AND id != :timetable_id
              AND start_time < :end_time
              AND end_time > :start_time
            LIMIT 1
            """
        ),
        values,
    ).first()

    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This section already has a timetable entry during this time",
        )

    try:
        row = db.execute(
            text(
                """
                UPDATE timetables
                SET
                    section_id = :section_id,
                    subject_id = :subject_id,
                    staff_id = :staff_id,
                    day_of_week = :day_of_week,
                    start_time = :start_time,
                    end_time = :end_time,
                    room = :room,
                    status = :status
                WHERE id = :timetable_id
                RETURNING
                    id,
                    section_id,
                    subject_id,
                    staff_id,
                    day_of_week,
                    start_time,
                    end_time,
                    room,
                    status
                """
            ),
            values,
        ).mappings().first()

        db.commit()

        return dict(row)

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid section, subject, or staff reference",
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling service unavailable",
        ) from exc


# ---------------------------------------------------------
# DELETE TIMETABLE
# ---------------------------------------------------------
@router.delete(
    "/timetables/{timetable_id}",
)
def delete_timetable(
    timetable_id: int,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                """
                DELETE FROM timetables
                WHERE id = :timetable_id
                RETURNING id
                """
            ),
            {
                "timetable_id": timetable_id,
            },
        ).mappings().first()

        if not row:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Timetable not found",
            )

        db.commit()

        return {
            "success": True,
            "message": "Timetable deleted successfully",
            "id": row["id"],
        }

    except HTTPException:
        raise

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete timetable because class sessions already exist",
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling service unavailable",
        ) from exc


# =========================================================
# CLASS SESSIONS
# =========================================================

# ---------------------------------------------------------
# CREATE CLASS SESSION
# ---------------------------------------------------------
@router.post(
    "/sessions",
    response_model=ClassSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_class_session(
    session_data: ClassSessionCreate,
    db: Session = Depends(get_db),
):
    # Make sure timetable exists.
    timetable = db.execute(
        text(
            """
            SELECT id
            FROM timetables
            WHERE id = :timetable_id
            """
        ),
        {
            "timetable_id": session_data.timetable_id,
        },
    ).first()

    if not timetable:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable not found",
        )

    try:
        row = db.execute(
            text(
                """
                INSERT INTO class_sessions (
                    timetable_id,
                    session_date,
                    is_conducted,
                    remarks
                )
                VALUES (
                    :timetable_id,
                    :session_date,
                    :is_conducted,
                    :remarks
                )
                RETURNING
                    id,
                    timetable_id,
                    session_date,
                    is_conducted,
                    remarks
                """
            ),
            {
                "timetable_id": session_data.timetable_id,
                "session_date": session_data.session_date,
                "is_conducted": session_data.is_conducted,
                "remarks": session_data.remarks,
            },
        ).mappings().first()

        db.commit()

        return dict(row)

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A class session already exists for this timetable and date",
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling service unavailable",
        ) from exc


# ---------------------------------------------------------
# GET ALL CLASS SESSIONS
# ---------------------------------------------------------
@router.get(
    "/sessions",
    response_model=list[ClassSessionResponse],
)
def get_class_sessions(
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    timetable_id,
                    session_date,
                    is_conducted,
                    remarks
                FROM class_sessions
                ORDER BY session_date DESC, id DESC
                """
            )
        ).mappings().all()

        return [dict(row) for row in rows]

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling service unavailable",
        ) from exc


# ---------------------------------------------------------
# GET SINGLE CLASS SESSION
# ---------------------------------------------------------
@router.get(
    "/sessions/{session_id}",
    response_model=ClassSessionResponse,
)
def get_class_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    row = db.execute(
        text(
            """
            SELECT
                id,
                timetable_id,
                session_date,
                is_conducted,
                remarks
            FROM class_sessions
            WHERE id = :session_id
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

    return dict(row)


# ---------------------------------------------------------
# UPDATE CLASS SESSION
# ---------------------------------------------------------
@router.put(
    "/sessions/{session_id}",
    response_model=ClassSessionResponse,
)
def update_class_session(
    session_id: int,
    session_data: ClassSessionUpdate,
    db: Session = Depends(get_db),
):
    payload = {
        "timetable_id": session_data.timetable_id,
        "session_date": session_data.session_date,
        "is_conducted": session_data.is_conducted,
        "remarks": session_data.remarks,
        "session_id": session_id,
    }

    set_clauses = []

    for field_name in [
        "timetable_id",
        "session_date",
        "is_conducted",
        "remarks",
    ]:
        if payload[field_name] is not None:
            set_clauses.append(
                f"{field_name} = :{field_name}"
            )

    if not set_clauses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No session fields were provided for update",
        )

    try:
        row = db.execute(
            text(
                f"""
                UPDATE class_sessions
                SET {', '.join(set_clauses)}
                WHERE id = :session_id
                RETURNING
                    id,
                    timetable_id,
                    session_date,
                    is_conducted,
                    remarks
                """
            ),
            payload,
        ).mappings().first()

        if not row:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class session not found",
            )

        db.commit()

        return dict(row)

    except HTTPException:
        raise

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A class session already exists for this timetable and date",
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling service unavailable",
        ) from exc


# ---------------------------------------------------------
# DELETE CLASS SESSION
# ---------------------------------------------------------
@router.delete(
    "/sessions/{session_id}",
)
def delete_class_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(
                """
                DELETE FROM class_sessions
                WHERE id = :session_id
                RETURNING id
                """
            ),
            {
                "session_id": session_id,
            },
        ).mappings().first()

        if not row:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class session not found",
            )

        db.commit()

        return {
            "success": True,
            "message": "Class session deleted successfully",
            "id": row["id"],
        }

    except HTTPException:
        raise

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete session because attendance records exist",
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling service unavailable",
        ) from exc