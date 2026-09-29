import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db

from schemas.attendance_schema import (
    AttendanceBulkCreate,
    AttendanceCreate,
    AttendanceResponse,
    AttendanceUpdate,
    ClassRosterResponse,
    StudentAttendanceReport,
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



def _roll_sort_key(student):
    roll = str(student.get("roll_number") or "")
    match = re.search(r"\d+", roll)

    return (
        int(match.group(0)) if match else 10**9,
        roll,
        str(student.get("name") or ""),
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
# CLASS ROSTER (grade + section + date -> students)
# =========================================================
# Lists every student of the class + section. When session_id is given,
# each student also carries the attendance already recorded for that
# session, so the same response can be used to mark or edit attendance.
#
# Must be declared before /{attendance_id}, otherwise "roster" would be
# parsed as an attendance id.

@router.get(
    "/roster",
    response_model=ClassRosterResponse,
)
def get_class_roster(
    grade_id: int = Query(...),
    section_id: int = Query(...),
    session_date: date = Query(...),
    session_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    klass = db.execute(
        text(
            """
            SELECT
                g.grade AS grade,
                sec.section AS section
            FROM grades g, sections sec
            WHERE g.id = :grade_id
              AND sec.id = :section_id
            """
        ),
        {
            "grade_id": grade_id,
            "section_id": section_id,
        },
    ).mappings().first()

    if not klass:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class or section not found",
        )

    if session_id is not None:
        session = db.execute(
            text(
                """
                SELECT
                    cs.id,
                    cs.session_date,
                    t.grade_id,
                    t.section_id
                FROM class_sessions cs
                JOIN timetables t ON t.id = cs.timetable_id
                WHERE cs.id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        ).mappings().first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class session not found",
            )

        if (
            session["session_date"] != session_date
            or session["grade_id"] != grade_id
            or session["section_id"] != section_id
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session does not belong to this class, section and date",
            )

    try:
        rows = db.execute(
            text(
                """
                SELECT *
                FROM students
                WHERE LOWER(TRIM(COALESCE(section, '')))
                      = LOWER(TRIM(:section))
                """
            ),
            {
                "section": klass["section"] or "",
            },
        ).mappings().all()

        context = {
            "section": klass["section"],
            "grade": klass["grade"],
        }

        students = [
            row for row in rows if _student_in_session_class(row, context)
        ]
        students.sort(key=_roll_sort_key)

        recorded = {}

        if session_id is not None:
            attendance_rows = db.execute(
                text(
                    """
                    SELECT id, student_id, status, remarks
                    FROM attendance
                    WHERE session_id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            ).mappings().all()

            recorded = {row["student_id"]: row for row in attendance_rows}

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attendance service unavailable",
        ) from exc

    items = []

    for student in students:
        record = recorded.get(student["id"])
        name = student.get("name")
        roll_number = student.get("roll_number")

        items.append(
            {
                "id": student["id"],
                "name": str(name) if name is not None else None,
                "roll_number": (
                    str(roll_number) if roll_number is not None else None
                ),
                "attendance_id": record["id"] if record else None,
                "status": record["status"] if record else None,
                "remarks": record["remarks"] if record else None,
            }
        )

    return {
        "grade_id": grade_id,
        "section_id": section_id,
        "grade": klass["grade"],
        "section": klass["section"],
        "session_date": session_date,
        "session_id": session_id,
        "total_students": len(items),
        "marked_students": len(recorded),
        "students": items,
    }


# =========================================================
# STUDENT ATTENDANCE REPORT (roll number -> percentage + every class)
# =========================================================
# Attended = PRESENT + LATE. Total = every class with an attendance record.
# A roll number can repeat across classes; pass grade_id + section_id to
# pick the right one (409 is returned when the match is ambiguous).
#
# Must be declared before /{attendance_id}.

@router.get(
    "/student-report",
    response_model=StudentAttendanceReport,
)
def get_student_attendance_report(
    roll_number: str = Query(...),
    grade_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    roll = roll_number.strip()

    if not roll:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a roll number",
        )

    if (grade_id is None) != (section_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide both grade_id and section_id, or neither",
        )

    try:
        candidates = db.execute(
            text(
                """
                SELECT *
                FROM students
                WHERE LOWER(TRIM(CAST(roll_number AS TEXT)))
                      = LOWER(TRIM(:roll_number))
                """
            ),
            {
                "roll_number": roll,
            },
        ).mappings().all()

        if grade_id is not None and section_id is not None:
            klass = db.execute(
                text(
                    """
                    SELECT
                        g.grade AS grade,
                        sec.section AS section
                    FROM grades g, sections sec
                    WHERE g.id = :grade_id
                      AND sec.id = :section_id
                    """
                ),
                {
                    "grade_id": grade_id,
                    "section_id": section_id,
                },
            ).mappings().first()

            if not klass:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Class or section not found",
                )

            candidates = [
                row
                for row in candidates
                if _student_in_session_class(row, klass)
            ]

        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No student found with this roll number",
            )

        if len(candidates) > 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="More than one student has this roll number. Select a grade and section",
            )

        student = candidates[0]

        rows = db.execute(
            text(
                """
                SELECT
                    a.id AS attendance_id,
                    a.session_id,
                    a.status,
                    a.remarks,
                    cs.session_date,
                    cs.subject_id,
                    cs.staff_id,
                    t.period_number,
                    t.start_time,
                    t.end_time
                FROM attendance a
                JOIN class_sessions cs ON cs.id = a.session_id
                JOIN timetables t ON t.id = cs.timetable_id
                WHERE a.student_id = :student_id
                ORDER BY
                    cs.session_date DESC,
                    t.period_number NULLS LAST,
                    t.start_time
                """
            ),
            {
                "student_id": student["id"],
            },
        ).mappings().all()

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Attendance service unavailable",
        ) from exc

    counts = {"PRESENT": 0, "ABSENT": 0, "LATE": 0, "EXCUSED": 0}

    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    total = len(rows)
    attended = counts["PRESENT"] + counts["LATE"]
    name = student.get("name")
    roll_value = student.get("roll_number")

    return {
        "student": {
            "id": student["id"],
            "name": str(name) if name is not None else None,
            "roll_number": str(roll_value) if roll_value is not None else None,
            "grade": student.get("grade"),
            "section": student.get("section"),
        },
        "total_classes": total,
        "attended_classes": attended,
        "present": counts["PRESENT"],
        "absent": counts["ABSENT"],
        "late": counts["LATE"],
        "excused": counts["EXCUSED"],
        "percentage": round(attended * 100 / total, 1) if total else 0.0,
        "records": [dict(row) for row in rows],
    }


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