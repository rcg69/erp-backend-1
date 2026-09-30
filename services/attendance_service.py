import re

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from schemas.attendance_schema import (
    AttendanceBulkCreate,
    AttendanceCreate,
    AttendanceUpdate,
)


def _normalize_grade(value):
    if value is None:
        return None

    value = str(value).strip().lower()

    if not value:
        return None

    match = re.search(r"\d+", value)

    if match:
        return match.group(0)

    return value


def _get_session_context(
    db: Session,
    session_id: int,
):
    row = db.execute(
        text(
            """
            SELECT
                cs.id,
                s.section,
                g.grade
            FROM class_sessions cs
            JOIN timetables t
                ON t.id = cs.timetable_id
            JOIN sections s
                ON s.id = t.section_id
            LEFT JOIN grades g
                ON g.id = t.grade_id
            WHERE cs.id = :session_id
            """
        ),
        {"session_id": session_id},
    ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Class session not found",
        )

    return row


def _student_in_session_class(
    student,
    context,
):
    student_section = (
        str(student["section"]).strip().lower()
        if student["section"] is not None
        else None
    )

    session_section = (
        str(context["section"]).strip().lower()
        if context["section"] is not None
        else None
    )

    if student_section != session_section:
        return False

    student_grade = _normalize_grade(student["grade"])
    session_grade = _normalize_grade(context["grade"])

    if (
        student_grade is not None
        and session_grade is not None
        and student_grade != session_grade
    ):
        return False

    return True


def _validate_students_for_session(
    db: Session,
    context,
    student_ids,
):
    rows = db.execute(
        text(
            """
            SELECT
                id,
                name,
                roll_number,
                section,
                grade
            FROM students
            WHERE id = ANY(:student_ids)
            """
        ),
        {"student_ids": student_ids},
    ).mappings().all()

    found_ids = {row["id"] for row in rows}

    for student_id in student_ids:
        if student_id not in found_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Student not found: {student_id}",
            )

    invalid_students = [
        str(row["id"])
        for row in rows
        if not _student_in_session_class(row, context)
    ]

    if invalid_students:
        raise HTTPException(
            status_code=400,
            detail=(
                "Student(s) not in this session's section: "
                + ", ".join(invalid_students)
            ),
        )

    return rows


def _roll_sort_key(student):
    roll = student["roll_number"]

    if roll is None:
        return (1, "", student["name"] or "")

    roll_text = str(roll).strip()

    if roll_text.isdigit():
        return (0, int(roll_text), roll_text)

    return (1, roll_text, student["name"] or "")


def create_attendance(
    attendance_data: AttendanceCreate,
    db: Session,
):
    try:
        context = _get_session_context(
            db,
            attendance_data.session_id,
        )

        _validate_students_for_session(
            db,
            context,
            [attendance_data.student_id],
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
            status_code=409,
            detail="Attendance already exists for this student and session",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail="Attendance service unavailable",
        ) from exc


def get_attendance(
    db: Session,
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
            status_code=503,
            detail="Attendance service unavailable",
        ) from exc


def get_class_roster(
    grade_id: int,
    section_id: int,
    session_date,
    session_id: int | None,
    db: Session,
):
    try:
        class_row = db.execute(
            text(
                """
                SELECT
                    g.id AS grade_id,
                    g.grade,
                    s.id AS section_id,
                    s.section
                FROM grades g
                JOIN sections s
                    ON s.id = :section_id
                WHERE g.id = :grade_id
                """
            ),
            {
                "grade_id": grade_id,
                "section_id": section_id,
            },
        ).mappings().first()

        if not class_row:
            raise HTTPException(
                status_code=404,
                detail="Class or section not found",
            )

        if session_id is not None:
            session_row = db.execute(
                text(
                    """
                    SELECT
                        cs.id,
                        cs.session_date,
                        t.grade_id,
                        t.section_id
                    FROM class_sessions cs
                    JOIN timetables t
                        ON t.id = cs.timetable_id
                    WHERE cs.id = :session_id
                    """
                ),
                {"session_id": session_id},
            ).mappings().first()

            if not session_row:
                raise HTTPException(
                    status_code=404,
                    detail="Class session not found",
                )

            if (
                session_row["session_date"] != session_date
                or session_row["grade_id"] != grade_id
                or session_row["section_id"] != section_id
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Session does not belong to this class, section and date",
                )

        students = db.execute(
            text(
                """
                SELECT
                    st.id,
                    st.name,
                    st.roll_number,
                    st.section,
                    st.grade
                FROM students st
                WHERE LOWER(TRIM(st.section)) =
                      LOWER(TRIM(:section))
                """
            ),
            {
                "section": class_row["section"],
            },
        ).mappings().all()

        students = [
            student
            for student in students
            if _student_in_session_class(
                student,
                class_row,
            )
        ]

        students = sorted(
            students,
            key=_roll_sort_key,
        )

        attendance_map = {}

        if session_id is not None:
            attendance_rows = db.execute(
                text(
                    """
                    SELECT
                        id,
                        student_id,
                        status,
                        remarks
                    FROM attendance
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id},
            ).mappings().all()

            attendance_map = {
                row["student_id"]: dict(row)
                for row in attendance_rows
            }

        student_items = []

        for student in students:
            attendance = attendance_map.get(student["id"])

            student_items.append(
                {
                    "id": student["id"],
                    "name": student["name"],
                    "roll_number": student["roll_number"],
                    "attendance_id": (
                        attendance["id"]
                        if attendance
                        else None
                    ),
                    "status": (
                        attendance["status"]
                        if attendance
                        else None
                    ),
                    "remarks": (
                        attendance["remarks"]
                        if attendance
                        else None
                    ),
                }
            )

        marked_students = sum(
            1
            for student in student_items
            if student["attendance_id"] is not None
        )

        return {
            "grade_id": grade_id,
            "section_id": section_id,
            "grade": class_row["grade"],
            "section": class_row["section"],
            "session_date": session_date,
            "session_id": session_id,
            "total_students": len(student_items),
            "marked_students": marked_students,
            "students": student_items,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Attendance service unavailable",
        ) from exc


def get_student_attendance_report(
    roll_number: str,
    grade_id: int | None,
    section_id: int | None,
    db: Session,
):
    roll_number = roll_number.strip()

    if not roll_number:
        raise HTTPException(
            status_code=400,
            detail="Enter a roll number",
        )

    if (grade_id is None) != (section_id is None):
        raise HTTPException(
            status_code=400,
            detail="Provide both grade_id and section_id, or neither",
        )

    try:
        candidates = db.execute(
            text(
                """
                SELECT
                    st.id,
                    st.name,
                    st.roll_number,
                    st.section,
                    st.grade
                FROM students st
                WHERE LOWER(TRIM(st.roll_number)) =
                      LOWER(TRIM(:roll_number))
                """
            ),
            {
                "roll_number": roll_number,
            },
        ).mappings().all()

        if grade_id is not None and section_id is not None:
            class_row = db.execute(
                text(
                    """
                    SELECT
                        g.id AS grade_id,
                        g.grade,
                        s.id AS section_id,
                        s.section
                    FROM grades g
                    JOIN sections s
                        ON s.id = :section_id
                    WHERE g.id = :grade_id
                    """
                ),
                {
                    "grade_id": grade_id,
                    "section_id": section_id,
                },
            ).mappings().first()

            if not class_row:
                raise HTTPException(
                    status_code=404,
                    detail="Class or section not found",
                )

            candidates = [
                student
                for student in candidates
                if _student_in_session_class(
                    student,
                    class_row,
                )
            ]

        if not candidates:
            raise HTTPException(
                status_code=404,
                detail="No student found with this roll number",
            )

        if len(candidates) > 1:
            raise HTTPException(
                status_code=409,
                detail=(
                    "More than one student has this roll number. "
                    "Select a grade and section"
                ),
            )

        student = candidates[0]

        records = db.execute(
            text(
                """
                SELECT
                    a.id,
                    a.session_id,
                    a.status,
                    a.remarks,
                    cs.session_date,
                    t.period_number,
                    t.start_time
                FROM attendance a
                JOIN class_sessions cs
                    ON cs.id = a.session_id
                JOIN timetables t
                    ON t.id = cs.timetable_id
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

        total = len(records)

        present = sum(
            1
            for record in records
            if str(record["status"]).upper() == "PRESENT"
        )

        absent = sum(
            1
            for record in records
            if str(record["status"]).upper() == "ABSENT"
        )

        late = sum(
            1
            for record in records
            if str(record["status"]).upper() == "LATE"
        )

        excused = sum(
            1
            for record in records
            if str(record["status"]).upper() == "EXCUSED"
        )

        attended = present + late

        percentage = (
            round((attended * 100) / total, 1)
            if total
            else 0.0
        )

        return {
            "student_id": student["id"],
            "name": student["name"],
            "roll_number": student["roll_number"],
            "grade": student["grade"],
            "section": student["section"],
            "total_classes": total,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": excused,
            "attendance_percentage": percentage,
            "records": [dict(record) for record in records],
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Attendance service unavailable",
        ) from exc


def get_attendance_record(
    attendance_id: int,
    db: Session,
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
            status_code=404,
            detail="Attendance record not found",
        )

    return dict(row)


def update_attendance(
    attendance_id: int,
    attendance_data: AttendanceUpdate,
    db: Session,
):
    update_data = attendance_data.model_dump(
        exclude_unset=True
    )

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No attendance fields were provided for update",
        )

    try:
        set_parts = []
        params = {
            "attendance_id": attendance_id,
        }

        if "status" in update_data:
            set_parts.append("status = :status")
            params["status"] = update_data["status"]

        if "remarks" in update_data:
            set_parts.append("remarks = :remarks")
            params["remarks"] = update_data["remarks"]

        row = db.execute(
            text(
                f"""
                UPDATE attendance
                SET {", ".join(set_parts)}
                WHERE id = :attendance_id
                RETURNING
                    id,
                    session_id,
                    student_id,
                    status,
                    remarks
                """
            ),
            params,
        ).mappings().first()

        if not row:
            db.rollback()

            raise HTTPException(
                status_code=404,
                detail="Attendance record not found",
            )

        db.commit()

        return dict(row)

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail="Attendance service unavailable",
        ) from exc


def delete_attendance(
    attendance_id: int,
    db: Session,
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
                status_code=404,
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
            status_code=503,
            detail="Attendance service unavailable",
        ) from exc


def create_bulk_attendance(
    attendance_data: AttendanceBulkCreate,
    db: Session,
):
    if not attendance_data.records:
        raise HTTPException(
            status_code=400,
            detail="Attendance records cannot be empty",
        )

    student_ids = [
        record.student_id
        for record in attendance_data.records
    ]

    for student_id in student_ids:
        if student_ids.count(student_id) > 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Duplicate student in attendance records: "
                    f"{student_id}"
                ),
            )

    try:
        context = _get_session_context(
            db,
            attendance_data.session_id,
        )

        _validate_students_for_session(
            db,
            context,
            student_ids,
        )

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

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Attendance already exists for one or more students",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail="Attendance service unavailable",
        ) from exc