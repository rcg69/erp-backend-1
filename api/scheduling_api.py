from datetime import time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db

from schemas.timetable_schema import (
    TimetableAssignment,
    TimetableCreate,
    TimetableOpenRequest,
    TimetableResponse,
    TimetableUpdate,
)

from schemas.class_session_schema import (
    ClassSessionCreate,
    ClassSessionResponse,
    ClassSessionUpdate,
    SessionGenerateRequest,
    SessionGenerateResponse,
)


router = APIRouter(
    prefix="/api/scheduling",
    tags=["Scheduling"]
)


# =========================================================
# CONSTANTS
# =========================================================

# Monday ... Saturday (1 = Monday, 7 = Sunday)
WORKING_DAYS = range(1, 7)

# Placeholder period times used when a grid is first opened.
# Each slot can be edited afterwards with PUT /timetables/{id}.
DEFAULT_PERIODS = {
    1: (time(9, 0), time(9, 50)),
    2: (time(9, 50), time(10, 40)),
    3: (time(10, 50), time(11, 40)),
    4: (time(11, 40), time(12, 30)),
    5: (time(13, 30), time(14, 20)),
    6: (time(14, 20), time(15, 10)),
}

# Guard against accidentally generating years of sessions.
MAX_GENERATE_DAYS = 400

TIMETABLE_COLUMNS = """
    id,
    section_id,
    grade_id,
    day_of_week,
    period_number,
    start_time,
    end_time,
    room,
    status,
    default_subject_id,
    default_staff_id,
    valid_from,
    valid_to
"""

SESSION_COLUMNS = """
    id,
    timetable_id,
    subject_id,
    staff_id,
    session_date,
    is_conducted,
    remarks
"""


# =========================================================
# TIMETABLES
# =========================================================


# ---------------------------------------------------------
# OPEN TIMETABLE (class + section -> 6 x 6 grid)
# ---------------------------------------------------------
# Idempotent: creates the 36 slots the first time and simply
# returns them on later calls. Existing slots keep their times
# and assignments; only the academic year dates are refreshed.
@router.post(
    "/timetables/open",
    response_model=list[TimetableResponse],
)
def open_timetable(
    open_data: TimetableOpenRequest,
    db: Session = Depends(get_db),
):
    grade = db.execute(
        text("SELECT id FROM grades WHERE id = :grade_id"),
        {"grade_id": open_data.grade_id},
    ).first()

    if not grade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found",
        )

    section = db.execute(
        text("SELECT id FROM sections WHERE id = :section_id"),
        {"section_id": open_data.section_id},
    ).first()

    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found",
        )

    slots = [
        {
            "grade_id": open_data.grade_id,
            "section_id": open_data.section_id,
            "day_of_week": day,
            "period_number": period,
            "start_time": start,
            "end_time": end,
            "valid_from": open_data.valid_from,
            "valid_to": open_data.valid_to,
        }
        for day in WORKING_DAYS
        for period, (start, end) in DEFAULT_PERIODS.items()
    ]

    try:
        db.execute(
            text(
                """
                INSERT INTO timetables (
                    grade_id,
                    section_id,
                    day_of_week,
                    period_number,
                    start_time,
                    end_time,
                    status,
                    valid_from,
                    valid_to
                )
                VALUES (
                    :grade_id,
                    :section_id,
                    :day_of_week,
                    :period_number,
                    :start_time,
                    :end_time,
                    'active',
                    :valid_from,
                    :valid_to
                )
                ON CONFLICT (
                    grade_id,
                    section_id,
                    day_of_week,
                    period_number
                )
                DO UPDATE SET
                    valid_from = EXCLUDED.valid_from,
                    valid_to = EXCLUDED.valid_to
                """
            ),
            slots,
        )

        rows = db.execute(
            text(
                f"""
                SELECT {TIMETABLE_COLUMNS}
                FROM timetables
                WHERE grade_id = :grade_id
                  AND section_id = :section_id
                ORDER BY day_of_week, period_number
                """
            ),
            {
                "grade_id": open_data.grade_id,
                "section_id": open_data.section_id,
            },
        ).mappings().all()

        db.commit()

        return [dict(row) for row in rows]

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling service unavailable",
        ) from exc


# ---------------------------------------------------------
# ASSIGN SUBJECT + STAFF TO A GRID SLOT
# ---------------------------------------------------------
@router.put(
    "/timetables/{timetable_id}/assignment",
    response_model=TimetableResponse,
)
def assign_timetable_slot(
    timetable_id: int,
    assignment: TimetableAssignment,
    db: Session = Depends(get_db),
):
    slot = db.execute(
        text("SELECT id FROM timetables WHERE id = :timetable_id"),
        {"timetable_id": timetable_id},
    ).first()

    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Timetable not found",
        )

    if assignment.subject_id is not None:
        subject = db.execute(
            text(
                """
                SELECT id
                FROM subjects
                WHERE id = :subject_id
                  AND status = 'active'
                """
            ),
            {"subject_id": assignment.subject_id},
        ).first()

        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subject not found or inactive",
            )

    if assignment.staff_id is not None:
        staff = db.execute(
            text(
                """
                SELECT id
                FROM staff
                WHERE id = :staff_id
                  AND status = 'active'
                """
            ),
            {"staff_id": assignment.staff_id},
        ).first()

        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff not found or inactive",
            )

        # The same teacher cannot be in two slots at the same time.
        staff_conflict = db.execute(
            text(
                """
                SELECT other.id
                FROM timetables other
                JOIN timetables me ON me.id = :timetable_id
                WHERE other.id != me.id
                  AND other.status = 'active'
                  AND other.default_staff_id = :staff_id
                  AND other.day_of_week = me.day_of_week
                  AND other.start_time < me.end_time
                  AND other.end_time > me.start_time
                LIMIT 1
                """
            ),
            {
                "timetable_id": timetable_id,
                "staff_id": assignment.staff_id,
            },
        ).first()

        if staff_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This staff member is already assigned to another class at this time",
            )

    try:
        row = db.execute(
            text(
                f"""
                UPDATE timetables
                SET
                    default_subject_id = :subject_id,
                    default_staff_id = :staff_id
                WHERE id = :timetable_id
                RETURNING {TIMETABLE_COLUMNS}
                """
            ),
            {
                "timetable_id": timetable_id,
                "subject_id": assignment.subject_id,
                "staff_id": assignment.staff_id,
            },
        ).mappings().first()

        db.commit()

        return dict(row)

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling service unavailable",
        ) from exc


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

    # Prevent overlapping timetable entries for the same class + section.
    conflict = db.execute(
        text(
            """
            SELECT id
            FROM timetables
            WHERE section_id = :section_id
              AND grade_id IS NOT DISTINCT FROM :grade_id
              AND day_of_week = :day_of_week
              AND status = 'active'
              AND start_time < :end_time
              AND end_time > :start_time
            LIMIT 1
            """
        ),
        {
            "section_id": timetable_data.section_id,
            "grade_id": timetable_data.grade_id,
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
                f"""
                INSERT INTO timetables (
                    section_id,
                    grade_id,
                    day_of_week,
                    period_number,
                    start_time,
                    end_time,
                    room,
                    status
                )
                VALUES (
                    :section_id,
                    :grade_id,
                    :day_of_week,
                    :period_number,
                    :start_time,
                    :end_time,
                    :room,
                    :status
                )
                RETURNING {TIMETABLE_COLUMNS}
                """
            ),
            {
                "section_id": timetable_data.section_id,
                "grade_id": timetable_data.grade_id,
                "day_of_week": timetable_data.day_of_week,
                "period_number": timetable_data.period_number,
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
            detail="Invalid section/class reference or duplicate period slot",
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
    grade_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text(
                f"""
                SELECT {TIMETABLE_COLUMNS}
                FROM timetables
                WHERE (CAST(:grade_id AS integer) IS NULL
                       OR grade_id = CAST(:grade_id AS integer))
                  AND (CAST(:section_id AS integer) IS NULL
                       OR section_id = CAST(:section_id AS integer))
                ORDER BY
                    section_id,
                    day_of_week,
                    period_number NULLS LAST,
                    start_time
                """
            ),
            {
                "grade_id": grade_id,
                "section_id": section_id,
            },
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
            f"""
            SELECT {TIMETABLE_COLUMNS}
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
                grade_id,
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
        "grade_id": current["grade_id"],
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
              AND grade_id IS NOT DISTINCT FROM :grade_id
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
                f"""
                UPDATE timetables
                SET
                    section_id = :section_id,
                    day_of_week = :day_of_week,
                    start_time = :start_time,
                    end_time = :end_time,
                    room = :room,
                    status = :status
                WHERE id = :timetable_id
                RETURNING {TIMETABLE_COLUMNS}
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
            detail="Invalid section reference or duplicate period slot",
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
    # class_sessions.timetable_id is ON DELETE CASCADE, and attendance
    # cascades from sessions. Without this check, deleting a slot would
    # silently wipe its sessions and all attendance recorded for them.
    has_sessions = db.execute(
        text(
            """
            SELECT 1
            FROM class_sessions
            WHERE timetable_id = :timetable_id
            LIMIT 1
            """
        ),
        {
            "timetable_id": timetable_id,
        },
    ).first()

    if has_sessions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete timetable because class sessions already exist",
        )

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
# GENERATE CLASS SESSIONS FROM THE WEEKLY GRID
# ---------------------------------------------------------
# Creates one dated class_sessions row for every assigned slot on every
# matching weekday in the date range. Safe to run repeatedly: dates that
# already have a session are left untouched (so substitutions and
# attendance are never overwritten).
@router.post(
    "/sessions/generate",
    response_model=SessionGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_class_sessions(
    generate_data: SessionGenerateRequest,
    db: Session = Depends(get_db),
):
    summary = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE default_subject_id IS NOT NULL
                      AND default_staff_id IS NOT NULL
                ) AS assigned,
                MIN(valid_from) AS valid_from,
                MAX(valid_to) AS valid_to
            FROM timetables
            WHERE grade_id = :grade_id
              AND section_id = :section_id
              AND status = 'active'
            """
        ),
        {
            "grade_id": generate_data.grade_id,
            "section_id": generate_data.section_id,
        },
    ).mappings().first()

    if not summary or summary["total"] == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No timetable found for this class and section. Open the timetable first",
        )

    if summary["assigned"] == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assign a subject and staff to at least one slot before generating sessions",
        )

    start_date = generate_data.start_date or summary["valid_from"]
    end_date = generate_data.end_date or summary["valid_to"]

    if start_date is None or end_date is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide start_date and end_date",
        )

    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be on or after start date",
        )

    if end_date - start_date > timedelta(days=MAX_GENERATE_DAYS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Date range cannot exceed {MAX_GENERATE_DAYS} days",
        )

    try:
        created = db.execute(
            text(
                """
                INSERT INTO class_sessions (
                    timetable_id,
                    subject_id,
                    staff_id,
                    session_date,
                    is_conducted
                )
                SELECT
                    t.id,
                    t.default_subject_id,
                    t.default_staff_id,
                    CAST(d AS date),
                    FALSE
                FROM timetables t
                CROSS JOIN generate_series(
                    CAST(:start_date AS date),
                    CAST(:end_date AS date),
                    INTERVAL '1 day'
                ) AS d
                WHERE t.grade_id = :grade_id
                  AND t.section_id = :section_id
                  AND t.status = 'active'
                  AND t.default_subject_id IS NOT NULL
                  AND t.default_staff_id IS NOT NULL
                  AND EXTRACT(ISODOW FROM d) = t.day_of_week
                  AND NOT (
                      CAST(d AS date) = ANY(CAST(:skip_dates AS date[]))
                  )
                ON CONFLICT (timetable_id, session_date) DO NOTHING
                RETURNING id
                """
            ),
            {
                "grade_id": generate_data.grade_id,
                "section_id": generate_data.section_id,
                "start_date": start_date,
                "end_date": end_date,
                "skip_dates": list(generate_data.skip_dates),
            },
        ).all()

        db.commit()

        return {
            "success": True,
            "message": "Class sessions generated successfully",
            "created": len(created),
            "assigned_slots": summary["assigned"],
            "unassigned_slots": summary["total"] - summary["assigned"],
            "start_date": start_date,
            "end_date": end_date,
        }

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduling service unavailable",
        ) from exc


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

    # Make sure subject exists.
    subject = db.execute(
        text(
            """
            SELECT id
            FROM subjects
            WHERE id = :subject_id
              AND status = 'active'
            """
        ),
        {"subject_id": session_data.subject_id},
    ).first()

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found or inactive",
        )

    # Make sure staff exists.
    staff = db.execute(
        text(
            """
            SELECT id
            FROM staff
            WHERE id = :staff_id
              AND status = 'active'
            """
        ),
        {"staff_id": session_data.staff_id},
    ).first()

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff not found or inactive",
        )

    try:
        row = db.execute(
            text(
                f"""
                INSERT INTO class_sessions (
                    timetable_id,
                    subject_id,
                    staff_id,
                    session_date,
                    is_conducted,
                    remarks
                )
                VALUES (
                    :timetable_id,
                    :subject_id,
                    :staff_id,
                    :session_date,
                    :is_conducted,
                    :remarks
                )
                RETURNING {SESSION_COLUMNS}
                """
            ),
            {
                "timetable_id": session_data.timetable_id,
                "subject_id": session_data.subject_id,
                "staff_id": session_data.staff_id,
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
                f"""
                SELECT {SESSION_COLUMNS}
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
    # Previously this query omitted subject_id / staff_id, which the
    # response model requires, so every call failed validation.
    row = db.execute(
        text(
            f"""
            SELECT {SESSION_COLUMNS}
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
        "subject_id": session_data.subject_id,
        "staff_id": session_data.staff_id,
        "session_date": session_data.session_date,
        "is_conducted": session_data.is_conducted,
        "remarks": session_data.remarks,
        "session_id": session_id,
    }

    set_clauses = []

    for field_name in [
        "timetable_id",
        "subject_id",
        "staff_id",
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
                RETURNING {SESSION_COLUMNS}
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
    # attendance.session_id is ON DELETE CASCADE, so the database would
    # not raise an IntegrityError here. Check explicitly instead of
    # silently deleting attendance records.
    has_attendance = db.execute(
        text(
            """
            SELECT 1
            FROM attendance
            WHERE session_id = :session_id
            LIMIT 1
            """
        ),
        {
            "session_id": session_id,
        },
    ).first()

    if has_attendance:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete session because attendance records exist",
        )

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