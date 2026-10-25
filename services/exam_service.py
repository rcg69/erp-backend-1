import logging
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from models import exam_model as model
from schemas.exam_schema import (
    ExamCreate,
    ExamSubjectCreate,
    ExamSubjectUpdate,
    ExamUpdate,
    MarksCorrection,
    StudentMarkEntry,
)


logger = logging.getLogger(__name__)


def _raise_database_error(exc, operation):
    logger.exception("Database error during exam %s", operation)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Exam service temporarily unavailable",
    ) from exc


def _require_exam(db: Session, exam_id: int):
    exam = model.get_exam(db, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


def _lock_exam(db: Session, exam_id: int):
    if model.lock_exam(db, exam_id) is None:
        raise HTTPException(status_code=404, detail="Exam not found")
    return _require_exam(db, exam_id)


def _require_exam_subject(db: Session, exam_subject_id: int):
    exam_subject = model.get_exam_subject(db, exam_subject_id)
    if exam_subject is None:
        raise HTTPException(status_code=404, detail="Exam subject not found")
    return exam_subject


def _require_draft(exam):
    if exam["status"] != "draft":
        raise HTTPException(
            status_code=409,
            detail="Only draft exams can be edited",
        )


def _validate_exam_subject_date(exam, exam_date):
    if exam_date is not None and not (
        exam["start_date"] <= exam_date <= exam["end_date"]
    ):
        raise HTTPException(
            status_code=422,
            detail="Subject exam_date must fall within the exam date range",
        )


def create_exam(data: ExamCreate, current_user: dict, db: Session):
    if data.end_date < data.start_date:
        raise HTTPException(422, "end_date must be on or after start_date")
    try:
        class_row = model.get_grade_class(
            db, data.grade_id, data.academic_year
        )
        if class_row is None:
            raise HTTPException(
                422,
                "The selected active class does not match the academic year",
            )
        exam = model.create_exam(
            db,
            {
                **data.model_dump(),
                "academic_year": class_row["academic_year"],
                "grade": class_row["grade"],
                "section_id": class_row["section_id"],
                "section": class_row["section"],
                "created_by": current_user["id"],
            },
        )
        if exam is None:
            raise HTTPException(500, "Exam could not be created")
        students = model.get_active_students_for_class(
            db, class_row["grade"], class_row["section"]
        )
        model.add_exam_students(
            db, exam["id"], [student["id"] for student in students]
        )
        db.commit()
        return exam
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Exam creation conflicted with a database constraint", exc_info=True)
        raise HTTPException(409, "Exam could not be created due to a conflict") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "creation")


def sync_exam_roster(exam_id: int, db: Session):
    try:
        exam = _lock_exam(db, exam_id)
        _require_draft(exam)
        class_row = model.get_grade_class(
            db, exam["grade_id"], exam["academic_year"]
        )
        if (
            class_row is None
            or class_row["grade"] != exam["grade"]
            or class_row["section_id"] != exam["section_id"]
        ):
            raise HTTPException(
                409,
                "The exam's class is no longer active; roster cannot be synchronized",
            )
        students = model.get_active_students_for_class(
            db, exam["grade"], exam["section"]
        )
        added_count = model.add_exam_students(
            db, exam_id, [student["id"] for student in students]
        )
        total_count = model.count_exam_students(db, exam_id)
        db.commit()
        return {
            "exam_id": exam_id,
            "added_students": added_count,
            "total_students": total_count,
        }
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "roster synchronization")


def list_exams(
    academic_year: str | None,
    grade_id: int | None,
    exam_status: str | None,
    limit: int,
    offset: int,
    db: Session,
):
    try:
        return model.list_exams(
            db, academic_year, grade_id, exam_status, limit, offset
        )
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "listing")


def get_exam(exam_id: int, db: Session):
    try:
        return _require_exam(db, exam_id)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "retrieval")


def update_exam(exam_id: int, data: ExamUpdate, db: Session):
    payload = data.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(400, "No exam fields were provided for update")
    if any(
        payload.get(field) is None
        for field in ("name", "start_date", "end_date")
        if field in payload
    ):
        raise HTTPException(
            422, "name, start_date, and end_date cannot be null"
        )
    try:
        exam = _lock_exam(db, exam_id)
        _require_draft(exam)
        start_date = payload.get("start_date", exam["start_date"])
        end_date = payload.get("end_date", exam["end_date"])
        if end_date < start_date:
            raise HTTPException(422, "end_date must be on or after start_date")
        for exam_subject in model.get_exam_subjects(db, exam_id):
            _validate_exam_subject_date(exam, exam_subject["exam_date"])
            exam_date = exam_subject["exam_date"]
            if exam_date is not None and not start_date <= exam_date <= end_date:
                raise HTTPException(
                    409,
                    "Exam date range cannot exclude a configured subject exam_date",
                )
        updated = model.update_exam(db, exam_id, payload)
        db.commit()
        return updated
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "update")


def delete_exam(exam_id: int, db: Session):
    try:
        exam = _lock_exam(db, exam_id)
        _require_draft(exam)
        subjects = model.get_exam_subjects(db, exam_id)
        if any(subject["marked_count"] for subject in subjects):
            raise HTTPException(409, "An exam with marks cannot be deleted")
        model.delete_exam(db, exam_id)
        db.commit()
        return {"success": True, "message": "Draft exam deleted"}
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Exam deletion was blocked by related records", exc_info=True)
        raise HTTPException(409, "Exam has records that prevent deletion") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "deletion")


def add_exam_subject(
    exam_id: int,
    data: ExamSubjectCreate,
    db: Session,
):
    try:
        exam = _lock_exam(db, exam_id)
        _require_draft(exam)
        subject = model.get_subject(db, data.subject_id)
        if subject is None or subject["status"].strip().lower() != "active":
            raise HTTPException(422, "Select an existing active subject")
        staff = model.get_active_staff(db, data.evaluator_staff_id)
        if staff is None:
            raise HTTPException(422, "Select an active evaluating staff member")
        _validate_exam_subject_date(exam, data.exam_date)
        result = model.create_exam_subject(
            db, exam_id, data.model_dump()
        )
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Duplicate exam subject or invalid assignment", exc_info=True)
        raise HTTPException(
            409, "This subject is already configured for the exam"
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "subject configuration")


def list_exam_subjects(exam_id: int, db: Session):
    try:
        _require_exam(db, exam_id)
        return model.get_exam_subjects(db, exam_id)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "subject listing")


def update_exam_subject(
    exam_id: int,
    exam_subject_id: int,
    data: ExamSubjectUpdate,
    db: Session,
):
    payload = data.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(400, "No exam subject fields were provided")
    if any(
        payload.get(field) is None
        for field in ("max_marks", "pass_marks", "evaluator_staff_id")
        if field in payload
    ):
        raise HTTPException(
            422,
            "max_marks, pass_marks, and evaluator_staff_id cannot be null",
        )
    try:
        locked_subject = model.lock_exam_subject(db, exam_subject_id)
        if locked_subject is None or locked_subject["exam_id"] != exam_id:
            raise HTTPException(404, "Exam subject not found")
        exam = _require_exam(db, exam_id)
        if exam["status"] != "draft":
            if (
                exam["status"] != "scheduled"
                or locked_subject["evaluation_status"] == "completed"
                or set(payload) != {"evaluator_staff_id"}
            ):
                raise HTTPException(
                    409,
                    "Only evaluator reassignment is allowed after scheduling and before evaluation is completed",
                )
        exam_subject = _require_exam_subject(db, exam_subject_id)
        max_marks = payload.get("max_marks", exam_subject["max_marks"])
        pass_marks = payload.get("pass_marks", exam_subject["pass_marks"])
        if pass_marks > max_marks:
            raise HTTPException(422, "pass_marks cannot exceed max_marks")
        exam_date = payload.get("exam_date", exam_subject["exam_date"])
        _validate_exam_subject_date(exam, exam_date)
        if "evaluator_staff_id" in payload:
            if payload["evaluator_staff_id"] is None:
                raise HTTPException(422, "An active evaluating staff member is required")
            staff = model.get_active_staff(db, payload["evaluator_staff_id"])
            if staff is None:
                raise HTTPException(422, "Select an active evaluating staff member")
        updated = model.update_exam_subject(
            db, exam_subject_id, payload
        )
        db.commit()
        return updated
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Exam subject update conflicted") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "subject update")


def delete_exam_subject(
    exam_id: int,
    exam_subject_id: int,
    db: Session,
):
    try:
        exam = _lock_exam(db, exam_id)
        _require_draft(exam)
        exam_subject = _require_exam_subject(db, exam_subject_id)
        if exam_subject["exam_id"] != exam_id:
            raise HTTPException(404, "Exam subject not found")
        if exam_subject["marked_count"]:
            raise HTTPException(409, "An exam subject with marks cannot be deleted")
        model.delete_exam_subject(db, exam_subject_id)
        db.commit()
        return {"success": True, "message": "Exam subject deleted"}
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Exam subject has related records") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "subject deletion")


def schedule_exam(exam_id: int, db: Session):
    try:
        exam = _lock_exam(db, exam_id)
        _require_draft(exam)
        subjects = model.get_exam_subjects(db, exam_id)
        if not subjects:
            raise HTTPException(409, "Configure at least one subject before scheduling")
        if subjects[0]["student_count"] < 1:
            raise HTTPException(409, "The exam class has no active students")
        model.set_exam_status(db, exam_id, "scheduled")
        db.commit()
        return _require_exam(db, exam_id)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "scheduling")


def list_assigned_subjects(
    staff_id: int,
    limit: int,
    offset: int,
    db: Session,
):
    try:
        return model.get_assigned_exam_subjects(
            db, staff_id, limit, offset
        )
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "assigned exam listing")


def get_assigned_roster(
    exam_subject_id: int,
    staff_id: int,
    limit: int,
    offset: int,
    db: Session,
):
    try:
        exam_subject = _require_exam_subject(db, exam_subject_id)
        if exam_subject["evaluator_staff_id"] != staff_id:
            raise HTTPException(404, "Assigned exam subject not found")
        return {
            "exam_subject": exam_subject,
            "students": model.get_assigned_roster(
                db, exam_subject_id, staff_id, limit, offset
            ),
        }
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "assigned roster retrieval")


def get_evaluation_progress(
    exam_subject_id: int,
    staff_id: int | None,
    db: Session,
):
    try:
        exam_subject = _require_exam_subject(db, exam_subject_id)
        if staff_id is not None and exam_subject["evaluator_staff_id"] != staff_id:
            raise HTTPException(404, "Assigned exam subject not found")
        return model.get_exam_subject_progress(db, exam_subject_id)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "progress retrieval")


def _validate_mark_payload(payload: dict, max_marks: Decimal):
    marks = payload["marks_obtained"]
    if payload["is_absent"]:
        if marks is not None:
            raise HTTPException(422, "Absent students cannot have marks")
    elif marks is None:
        raise HTTPException(422, "marks_obtained is required unless the student is absent")
    elif marks < 0 or marks > max_marks:
        raise HTTPException(
            422, f"marks_obtained must be between 0 and {max_marks}"
        )


def enter_student_marks(
    exam_subject_id: int,
    student_id: int,
    data: StudentMarkEntry,
    current_user: dict,
    staff_id: int,
    db: Session,
):
    payload = data.model_dump()
    try:
        exam_subject = model.lock_exam_subject(db, exam_subject_id)
        if exam_subject is None or exam_subject["evaluator_staff_id"] != staff_id:
            raise HTTPException(404, "Assigned exam subject not found")
        if exam_subject["exam_status"] != "scheduled":
            raise HTTPException(409, "Marks can only be entered for a scheduled exam")
        if exam_subject["evaluation_status"] == "completed":
            raise HTTPException(409, "Evaluation is completed and locked")
        if not model.get_exam_student(
            db, exam_subject["exam_id"], student_id
        ):
            raise HTTPException(400, "Student is not in this exam's class roster")
        _validate_mark_payload(payload, exam_subject["max_marks"])
        action = (
            "updated"
            if model.get_mark(db, exam_subject_id, student_id)
            else "created"
        )
        model.save_mark(
            db,
            exam_subject_id,
            student_id,
            payload,
            current_user["id"],
            None,
            action,
        )
        if exam_subject["evaluation_status"] == "pending":
            model.set_evaluation_status(
                db, exam_subject_id, "in_progress"
            )
        response = model.get_mark_response(
            db, exam_subject_id, student_id
        )
        db.commit()
        return response
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Student mark write conflicted", exc_info=True)
        raise HTTPException(409, "Mark could not be saved due to a conflict") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "marks entry")


def complete_evaluation(
    exam_subject_id: int,
    staff_id: int,
    db: Session,
):
    try:
        exam_subject = model.lock_exam_subject(db, exam_subject_id)
        if exam_subject is None or exam_subject["evaluator_staff_id"] != staff_id:
            raise HTTPException(404, "Assigned exam subject not found")
        if exam_subject["exam_status"] != "scheduled":
            raise HTTPException(409, "Exam is not open for evaluation")
        if exam_subject["evaluation_status"] == "completed":
            progress = model.get_exam_subject_progress(db, exam_subject_id)
            db.commit()
            return progress
        total_students = model.count_exam_students(db, exam_subject["exam_id"])
        marked_students = model.count_subject_marks(db, exam_subject_id)
        if total_students == 0 or marked_students != total_students:
            raise HTTPException(
                409,
                "Enter marks or mark absent for every student before completing evaluation",
            )
        model.set_evaluation_status(db, exam_subject_id, "completed")
        if model.all_subjects_completed(db, exam_subject["exam_id"]):
            model.set_exam_status(db, exam_subject["exam_id"], "completed")
        db.commit()
        return model.get_exam_subject_progress(db, exam_subject_id)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "evaluation completion")


def correct_student_marks(
    exam_subject_id: int,
    student_id: int,
    data: MarksCorrection,
    current_user: dict,
    db: Session,
):
    payload = data.model_dump(exclude={"reason"})
    reason = data.reason.strip()
    if not reason:
        raise HTTPException(422, "A correction reason is required")
    try:
        exam_subject = model.lock_exam_subject(db, exam_subject_id)
        if exam_subject is None:
            raise HTTPException(404, "Exam subject not found")
        if exam_subject["exam_status"] == "draft":
            raise HTTPException(
                409, "Marks cannot be corrected before the exam is scheduled"
            )
        if not model.get_exam_student(
            db, exam_subject["exam_id"], student_id
        ):
            raise HTTPException(404, "Student is not in this exam's roster")
        _validate_mark_payload(payload, exam_subject["max_marks"])
        model.save_mark(
            db,
            exam_subject_id,
            student_id,
            payload,
            current_user["id"],
            reason,
            "correction",
        )
        response = model.get_mark_response(
            db, exam_subject_id, student_id
        )
        db.commit()
        return response
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Mark correction conflicted") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "marks correction")


def publish_exam(exam_id: int, db: Session):
    try:
        exam = _lock_exam(db, exam_id)
        if exam["status"] != "completed":
            raise HTTPException(
                409, "All subject evaluations must be completed before publishing"
            )
        subjects = model.get_exam_subjects(db, exam_id)
        if not subjects or any(
            subject["evaluation_status"] != "completed"
            or subject["marked_count"] != subject["student_count"]
            for subject in subjects
        ):
            raise HTTPException(
                409, "All students must have marks before publishing"
            )
        model.set_exam_status(db, exam_id, "published")
        db.commit()
        return _require_exam(db, exam_id)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        _raise_database_error(exc, "publication")


def get_exam_results(
    exam_id: int,
    current_user: dict,
    limit: int,
    offset: int,
    db: Session,
):
    try:
        role = model.get_role_name(db, current_user["role_id"])
        if role == "admin":
            student_id = None
            staff_id = None
        elif role == "student":
            student_id = current_user.get("person_id")
            staff_id = None
            if student_id is None:
                raise HTTPException(403, "Student account is not linked to a student")
            exam = model.get_exam_ids_for_student(db, student_id, exam_id)
            if exam is None:
                raise HTTPException(404, "Exam result not found")
            if exam["status"] != "published":
                raise HTTPException(403, "Exam results have not been published")
        elif role in {"staff", "teacher"}:
            student_id = None
            staff_id = current_user.get("person_id")
            if staff_id is None:
                raise HTTPException(403, "Staff account is not linked to a staff profile")
            if model.get_active_staff(db, staff_id) is None:
                raise HTTPException(403, "Staff profile is missing or inactive")
            exam = model.get_exam(db, exam_id)
            if exam is None:
                raise HTTPException(404, "Exam not found")
            if exam["status"] != "published":
                raise HTTPException(403, "Exam results have not been published")
            if not model.has_staff_assignment(db, exam_id, staff_id):
                raise HTTPException(404, "Exam results not found")
        else:
            raise HTTPException(403, "Exam results are not available to this role")

        rows = model.get_results(
            db, exam_id, student_id, staff_id, limit, offset
        )
        if not rows:
            exam = model.get_exam(db, exam_id)
            if exam is None:
                raise HTTPException(404, "Exam not found")
            if role == "student":
                raise HTTPException(404, "Exam result not found")
            return {
                "exam_id": exam["id"],
                "exam_name": exam["name"],
                "academic_year": exam["academic_year"],
                "status": exam["status"],
                "students": [],
            }

        students = {}
        for row in rows:
            result = students.setdefault(
                row["student_id"],
                {
                    "student_id": row["student_id"],
                    "student_name": row["student_name"],
                    "roll_number": row["roll_number"],
                    "subjects": [],
                },
            )
            result["subjects"].append({
                "subject_id": row["subject_id"],
                "subject_name": row["subject_name"],
                "max_marks": row["max_marks"],
                "pass_marks": row["pass_marks"],
                "marks_obtained": row["marks_obtained"],
                "is_absent": row["is_absent"],
                "remarks": row["remarks"],
            })
        first = rows[0]
        return {
            "exam_id": first["exam_id"],
            "exam_name": first["exam_name"],
            "academic_year": first["academic_year"],
            "status": first["status"],
            "students": list(students.values()),
        }
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        _raise_database_error(exc, "results retrieval")
