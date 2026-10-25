
import re
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session


ATTENDANCE_COLUMNS = """
    id, session_id, student_id, academic_year, status, remarks
"""


def _dict(row):
    return dict(row) if row is not None else None


def _dicts(rows):
    return [dict(row) for row in rows]


def get_session_context(db: Session, session_id: int):
    row = db.execute(
        text("""
            SELECT cs.id, sec.section, g.grade, g.academic_year
            FROM class_sessions cs
            JOIN timetables t ON t.id = cs.timetable_id
            JOIN sections sec ON sec.id = t.section_id
            LEFT JOIN grades g ON g.id = t.grade_id
            WHERE cs.id = :session_id
        """),
        {"session_id": session_id},
    ).mappings().first()
    return _dict(row)


def get_class(db: Session, grade_id: int, section_id: int):
    row = db.execute(
        text("""
            SELECT g.id AS grade_id, g.grade, g.academic_year,
                   sec.id AS section_id, sec.section
            FROM grades g
            CROSS JOIN sections sec
            WHERE g.id = :grade_id
              AND sec.id = :section_id
              AND (g.section_id IS NULL OR g.section_id = sec.id)
        """),
        {"grade_id": grade_id, "section_id": section_id},
    ).mappings().first()
    return _dict(row)


def get_class_session(db: Session, session_id: int):
    row = db.execute(
        text("""
            SELECT
                cs.id, cs.session_date, t.grade_id, t.section_id,
                g.academic_year
            FROM class_sessions cs
            JOIN timetables t ON t.id = cs.timetable_id
            LEFT JOIN grades g ON g.id = t.grade_id
            WHERE cs.id = :session_id
        """),
        {"session_id": session_id},
    ).mappings().first()
    return _dict(row)


def get_students_by_ids(db: Session, student_ids: list[int]):
    if not student_ids:
        return []
    rows = db.execute(
        text("""
            SELECT id, name, roll_number, section, grade
            FROM students
            WHERE id = ANY(:student_ids)
        """),
        {"student_ids": student_ids},
    ).mappings().all()
    return _dicts(rows)


def get_students_by_section(db: Session, section: str):
    rows = db.execute(
        text("""
            SELECT id, name, roll_number, section, grade
            FROM students
            WHERE LOWER(TRIM(COALESCE(section, '')))
                = LOWER(TRIM(:section))
        """),
        {"section": section or ""},
    ).mappings().all()
    return _dicts(rows)


def get_student_candidates_by_roll(db: Session, roll_number: str):
    rows = db.execute(
        text("""
            SELECT id, name, roll_number, section, grade
            FROM students
            WHERE LOWER(TRIM(CAST(roll_number AS TEXT)))
                = LOWER(TRIM(:roll_number))
        """),
        {"roll_number": roll_number},
    ).mappings().all()
    return _dicts(rows)


def get_attendance_for_session(db: Session, session_id: int):
    rows = db.execute(
        text("""
            SELECT id, student_id, academic_year, status, remarks
            FROM attendance
            WHERE session_id = :session_id
        """),
        {"session_id": session_id},
    ).mappings().all()
    return _dicts(rows)


def get_current_academic_year_for_student(db: Session, student: dict):
    rows = db.execute(
        text("""
            SELECT DISTINCT g.academic_year
            FROM grades g
            JOIN sections sec ON sec.id = g.section_id
            WHERE LOWER(TRIM(g.grade)) = LOWER(TRIM(:grade))
              AND LOWER(TRIM(sec.section)) = LOWER(TRIM(:section))
              AND LOWER(g.status) = 'active'
            ORDER BY g.academic_year DESC
            LIMIT 2
        """),
        {
            "grade": student.get("grade") or "",
            "section": student.get("section") or "",
        },
    ).mappings().all()
    return [row["academic_year"] for row in rows]


def get_attendance_report_records(
    db: Session,
    student_id: int,
    academic_year: str,
):
    rows = db.execute(
        text("""
            SELECT
                a.id AS attendance_id,
                a.session_id,
                a.academic_year,
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
              AND a.academic_year = :academic_year
            ORDER BY cs.session_date DESC,
                     t.period_number NULLS LAST,
                     t.start_time
        """),
        {"student_id": student_id, "academic_year": academic_year},
    ).mappings().all()
    return _dicts(rows)


def get_all_attendance(db: Session, academic_year: str | None = None):
    rows = db.execute(
        text(f"""
            SELECT {ATTENDANCE_COLUMNS}
            FROM attendance
            WHERE CAST(:academic_year AS VARCHAR) IS NULL
               OR academic_year = :academic_year
            ORDER BY id DESC
        """),
        {"academic_year": academic_year},
    ).mappings().all()
    return _dicts(rows)


def get_attendance_by_id(db: Session, attendance_id: int):
    row = db.execute(
        text(f"""
            SELECT {ATTENDANCE_COLUMNS}
            FROM attendance
            WHERE id = :attendance_id
        """),
        {"attendance_id": attendance_id},
    ).mappings().first()
    return _dict(row)


def insert_attendance(db: Session, payload: dict):
    row = db.execute(
        text(f"""
            INSERT INTO attendance
                (session_id, student_id, academic_year, status, remarks)
            VALUES
                (:session_id, :student_id, :academic_year, :status, :remarks)
            RETURNING {ATTENDANCE_COLUMNS}
        """),
        payload,
    ).mappings().first()
    return _dict(row)


def insert_attendance_bulk_item(
    db: Session,
    session_id: int,
    record: dict,
):
    return insert_attendance(
        db,
        {
            "session_id": session_id,
            "student_id": record["student_id"],
            "academic_year": record["academic_year"],
            "status": record["status"],
            "remarks": record.get("remarks"),
        },
    )


def update_attendance_record(
    db: Session,
    attendance_id: int,
    payload: dict,
):
    allowed_fields = {"status", "remarks"}
    safe_payload = {
        key: value
        for key, value in payload.items()
        if key in allowed_fields
    }
    if not safe_payload:
        return None

    assignments = ", ".join(
        f"{field} = :{field}" for field in safe_payload
    )
    row = db.execute(
        text(f"""
            UPDATE attendance
            SET {assignments}
            WHERE id = :attendance_id
            RETURNING {ATTENDANCE_COLUMNS}
        """),
        {**safe_payload, "attendance_id": attendance_id},
    ).mappings().first()
    return _dict(row)


def delete_attendance_record(db: Session, attendance_id: int):
    row = db.execute(
        text("""
            DELETE FROM attendance
            WHERE id = :attendance_id
            RETURNING id
        """),
        {"attendance_id": attendance_id},
    ).mappings().first()
    return _dict(row)


def get_teacher_sessions(db: Session, session_date: date, staff_id: int):
    db.execute(
        text("""
            INSERT INTO class_sessions (
                timetable_id, subject_id, staff_id,
                session_date, is_conducted
            )
            SELECT
                t.id, t.default_subject_id, t.default_staff_id,
                :session_date, FALSE
            FROM timetables t
            WHERE t.default_staff_id = :staff_id
              AND t.default_subject_id IS NOT NULL
              AND t.status = 'active'
              AND t.day_of_week = :day_of_week
              AND (t.valid_from IS NULL OR t.valid_from <= :session_date)
              AND (t.valid_to IS NULL OR t.valid_to >= :session_date)
            ON CONFLICT (timetable_id, session_date) DO NOTHING
        """),
        {
            "session_date": session_date,
            "staff_id": staff_id,
            "day_of_week": session_date.isoweekday(),
        },
    )

    rows = db.execute(
        text("""
            SELECT
                cs.id AS session_id,
                cs.timetable_id,
                cs.session_date,
                t.grade_id,
                t.section_id,
                g.academic_year,
                g.grade,
                sec.section,
                cs.subject_id,
                sub.name AS subject_name,
                t.period_number,
                t.start_time,
                t.end_time,
                t.room,
                cs.is_conducted
            FROM class_sessions cs
            JOIN timetables t ON t.id = cs.timetable_id
            LEFT JOIN grades g ON g.id = t.grade_id
            JOIN sections sec ON sec.id = t.section_id
            JOIN subjects sub ON sub.id = cs.subject_id
            WHERE cs.staff_id = :staff_id
              AND cs.session_date = :session_date
            ORDER BY t.period_number NULLS LAST,
                     t.start_time, cs.id
        """),
        {"staff_id": staff_id, "session_date": session_date},
    ).mappings().all()
    return _dicts(rows)


def get_teacher_session_context(
    db: Session,
    session_id: int,
    staff_id: int,
):
    row = db.execute(
        text("""
            SELECT
                cs.id, cs.staff_id, cs.session_date,
                t.grade_id, t.section_id,
                g.grade, g.academic_year, sec.section
            FROM class_sessions cs
            JOIN timetables t ON t.id = cs.timetable_id
            LEFT JOIN grades g ON g.id = t.grade_id
            JOIN sections sec ON sec.id = t.section_id
            WHERE cs.id = :session_id
              AND cs.staff_id = :staff_id
        """),
        {"session_id": session_id, "staff_id": staff_id},
    ).mappings().first()
    return _dict(row)


def upsert_teacher_attendance(
    db: Session,
    session_id: int,
    record: dict,
):
    row = db.execute(
        text("""
            INSERT INTO attendance (
                session_id, student_id, academic_year, status, remarks
            )
            VALUES (
                :session_id, :student_id, :academic_year, :status, :remarks
            )
            ON CONFLICT (session_id, student_id)
            DO UPDATE SET
                status = EXCLUDED.status,
                remarks = EXCLUDED.remarks,
                academic_year = EXCLUDED.academic_year
            RETURNING id, session_id, student_id, academic_year, status, remarks
        """),
        {
            "session_id": session_id,
            "student_id": record["student_id"],
            "academic_year": record["academic_year"],
            "status": record["status"],
            "remarks": record.get("remarks"),
        },
    ).mappings().first()
    return _dict(row)


def mark_session_conducted(db: Session, session_id: int):
    db.execute(
        text("""
            UPDATE class_sessions
            SET is_conducted = TRUE
            WHERE id = :session_id
        """),
        {"session_id": session_id},
    )
