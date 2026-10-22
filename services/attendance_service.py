
import logging
import re
from collections import Counter
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from models import attendance_model as model
from schemas.attendance_schema import (
    AttendanceBulkCreate,
    AttendanceCreate,
    AttendanceUpdate,
    TeacherAttendanceBulkCreate,
)


logger = logging.getLogger(__name__)


def _normalize_grade(value):
    if value is None:
        return None
    value = str(value).strip().lower()
    if not value:
        return None
    match = re.search(r"\d+", value)
    return match.group(0) if match else value


def _student_in_class(student, context):
    student_section = (student.get("section") or "").strip().lower()
    class_section = (context.get("section") or "").strip().lower()

    if student_section != class_section:
        return False

    student_grade = _normalize_grade(student.get("grade"))
    class_grade = _normalize_grade(context.get("grade"))

    return not (
        student_grade
        and class_grade
        and student_grade != class_grade
    )


def _validate_students(db, context, student_ids):
    rows = model.get_students_by_ids(db, student_ids)
    found = {row["id"]: row for row in rows}
    missing = sorted(set(student_ids) - set(found))

    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found: "
            + ", ".join(map(str, missing)),
        )

    outside = [
        student_id
        for student_id in student_ids
        if not _student_in_class(found[student_id], context)
    ]

    if outside:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student(s) not in this session's section: "
            + ", ".join(map(str, outside)),
        )

    return rows


def _require_session(db, session_id):
    context = model.get_session_context(db, session_id)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found",
        )
    return context


def _require_teacher_session(db, session_id, staff_id):
    context = model.get_teacher_session_context(db, session_id, staff_id)
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class session not found or not assigned to this staff member",
        )
    return context


def _raise_database_error(exc, operation):
    logger.exception("Database error during attendance %s", operation)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Attendance service temporarily unavailable",
    ) from exc


def create_attendance(data: AttendanceCreate, db: Session):
    try:
        context = _require_session(db, data.session_id)
        _validate_students(db, context, [data.student_id])

        record = model.insert_attendance(
            db,
            {
                "session_id": data.session_id,
                "student_id": data.student_id,
                "status": data.status,
                "remarks": data.remarks,
            },
        )
        if record is None:
            raise HTTPException(500, "Attendance could not be created")

        db.commit()
        return record

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Duplicate or invalid attendance insert", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance already exists for this student and session",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "creation")


def get_attendance(db: Session):
    try:
        return model.get_all_attendance(db)
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "listing")


def get_one_attendance(attendance_id: int, db: Session):
    try:
        record = model.get_attendance_by_id(db, attendance_id)
        if record is None:
            raise HTTPException(404, "Attendance record not found")
        return record
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "retrieval")


def get_class_roster(
    grade_id: int,
    section_id: int,
    session_date: date,
    session_id: int | None,
    db: Session,
):
    try:
        klass = model.get_class(db, grade_id, section_id)
        if klass is None:
            raise HTTPException(404, "Class or section not found")

        if session_id is not None:
            session = model.get_class_session(db, session_id)
            if session is None:
                raise HTTPException(404, "Class session not found")

            if (
                session["session_date"] != session_date
                or session["grade_id"] != grade_id
                or session["section_id"] != section_id
            ):
                raise HTTPException(
                    400,
                    "Session does not belong to this class, section and date",
                )

        students = [
            student
            for student in model.get_students_by_section(
                db, klass["section"] or ""
            )
            if _student_in_class(student, klass)
        ]

        def roll_sort_key(student):
            roll = str(student.get("roll_number") or "").strip()
            match = re.search(r"\d+", roll)
            return (
                int(match.group()) if match else 10**9,
                roll.lower(),
                str(student.get("name") or "").lower(),
            )

        students.sort(key=roll_sort_key)

        recorded = (
            model.get_attendance_for_session(db, session_id)
            if session_id is not None
            else []
        )
        attendance_by_student = {
            row["student_id"]: row for row in recorded
        }

        roster = []
        for student in students:
            record = attendance_by_student.get(student["id"])
            roster.append({
                "id": student["id"],
                "name": student.get("name"),
                "roll_number": student.get("roll_number"),
                "attendance_id": record["id"] if record else None,
                "status": record["status"] if record else None,
                "remarks": record["remarks"] if record else None,
            })

        marked_count = sum(
            1 for item in roster if item["attendance_id"] is not None
        )

        return {
            "grade_id": grade_id,
            "section_id": section_id,
            "grade": klass["grade"],
            "section": klass["section"],
            "session_date": session_date,
            "session_id": session_id,
            "total_students": len(roster),
            "marked_students": marked_count,
            "students": roster,
        }

    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "roster retrieval")


def get_student_attendance_report(
    roll_number: str,
    grade_id: int | None,
    section_id: int | None,
    db: Session,
):
    roll_number = roll_number.strip()
    if not roll_number:
        raise HTTPException(400, "Enter a roll number")

    if (grade_id is None) != (section_id is None):
        raise HTTPException(
            400,
            "Provide both grade_id and section_id, or neither",
        )

    try:
        candidates = model.get_student_candidates_by_roll(db, roll_number)

        if grade_id is not None and section_id is not None:
            klass = model.get_class(db, grade_id, section_id)
            if klass is None:
                raise HTTPException(404, "Class or section not found")

            candidates = [
                student for student in candidates
                if _student_in_class(student, klass)
            ]

        if not candidates:
            raise HTTPException(
                404, "No student found with this roll number"
            )

        if len(candidates) > 1:
            raise HTTPException(
                409,
                "More than one student has this roll number. Select a grade and section",
            )

        student = candidates[0]
        records = model.get_attendance_report_records(db, student["id"])

        counts = Counter(str(row["status"]).upper() for row in records)
        total = len(records)
        attended = counts["PRESENT"] + counts["LATE"]

        return {
            "student": {
                "id": student["id"],
                "name": student.get("name"),
                "roll_number": student.get("roll_number"),
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
            "records": records,
        }

    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "report generation")


def update_attendance(
    attendance_id: int,
    data: AttendanceUpdate,
    db: Session,
):
    payload = data.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(
            400, "No attendance fields were provided for update"
        )

    try:
        existing = model.get_attendance_by_id(db, attendance_id)
        if existing is None:
            raise HTTPException(404, "Attendance record not found")

        updated = model.update_attendance_record(
            db, attendance_id, payload
        )
        if updated is None:
            raise HTTPException(400, "No valid attendance fields were provided")

        db.commit()
        return updated

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Attendance update violated a constraint", exc_info=True)
        raise HTTPException(409, "Attendance update conflicts with a database constraint") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "update")


def delete_attendance(attendance_id: int, db: Session):
    try:
        deleted = model.delete_attendance_record(db, attendance_id)
        if deleted is None:
            raise HTTPException(404, "Attendance record not found")

        db.commit()
        return {
            "success": True,
            "message": "Attendance deleted successfully",
            "id": deleted["id"],
        }

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "deletion")


def create_bulk_attendance(data: AttendanceBulkCreate, db: Session):
    if not data.records:
        raise HTTPException(400, "Attendance records cannot be empty")

    student_ids = [record.student_id for record in data.records]
    duplicates = sorted(
        student_id
        for student_id, count in Counter(student_ids).items()
        if count > 1
    )
    if duplicates:
        raise HTTPException(
            400,
            "Duplicate student in attendance records: "
            + ", ".join(map(str, duplicates)),
        )

    try:
        context = _require_session(db, data.session_id)
        _validate_students(db, context, student_ids)

        created = [
            model.insert_attendance_bulk_item(
                db, data.session_id, record.model_dump()
            )
            for record in data.records
        ]

        db.commit()
        return {
            "success": True,
            "message": "Attendance recorded successfully",
            "count": len(created),
            "records": created,
        }

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Bulk attendance insert conflicted", exc_info=True)
        raise HTTPException(
            409,
            "Attendance already exists for one or more students",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "bulk creation")


def get_teacher_class_sessions(
    session_date: date,
    staff_id: int,
    db: Session,
):
    try:
        sessions = model.get_teacher_sessions(db, session_date, staff_id)
        db.commit()
        return {"session_date": session_date, "classes": sessions}
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "teacher session retrieval")


def get_teacher_class_roster(
    session_id: int,
    staff_id: int,
    db: Session,
):
    try:
        context = _require_teacher_session(db, session_id, staff_id)
        students = [
            student
            for student in model.get_students_by_section(
                db, context["section"] or ""
            )
            if _student_in_class(student, context)
        ]

        def roll_sort_key(student):
            roll = str(student.get("roll_number") or "").strip()
            match = re.search(r"\d+", roll)
            return (
                int(match.group()) if match else 10**9,
                roll.lower(),
                str(student.get("name") or "").lower(),
            )

        students.sort(key=roll_sort_key)
        attendance = model.get_attendance_for_session(db, session_id)
        by_student = {row["student_id"]: row for row in attendance}

        roster = []
        for student in students:
            record = by_student.get(student["id"])
            roster.append({
                "id": student["id"],
                "name": student.get("name"),
                "roll_number": student.get("roll_number"),
                "attendance_id": record["id"] if record else None,
                "status": record["status"] if record else None,
                "remarks": record["remarks"] if record else None,
            })

        return {
            "grade_id": context["grade_id"],
            "section_id": context["section_id"],
            "grade": context["grade"],
            "section": context["section"],
            "session_date": context["session_date"],
            "session_id": session_id,
            "total_students": len(roster),
            "marked_students": sum(
                1 for row in roster if row["attendance_id"] is not None
            ),
            "students": roster,
        }

    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "teacher roster retrieval")


def save_teacher_class_attendance(
    session_id: int,
    staff_id: int,
    data: TeacherAttendanceBulkCreate,
    db: Session,
):
    student_ids = [record.student_id for record in data.records]
    duplicates = sorted(
        student_id
        for student_id, count in Counter(student_ids).items()
        if count > 1
    )
    if duplicates:
        raise HTTPException(
            400,
            "Duplicate student in attendance records: "
            + ", ".join(map(str, duplicates)),
        )

    try:
        context = _require_teacher_session(db, session_id, staff_id)
        _validate_students(db, context, student_ids)

        records = [
            model.upsert_teacher_attendance(
                db, session_id, record.model_dump()
            )
            for record in data.records
        ]
        model.mark_session_conducted(db, session_id)
        db.commit()

        return {
            "success": True,
            "message": "Attendance saved successfully",
            "session_id": session_id,
            "session_date": context["session_date"],
            "count": len(records),
            "records": records,
        }

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Teacher attendance save conflicted", exc_info=True)
        raise HTTPException(
            409,
            "Attendance could not be saved because of a conflicting record",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "teacher attendance save")
