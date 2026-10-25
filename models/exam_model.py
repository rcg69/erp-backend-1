from sqlalchemy import text
from sqlalchemy.orm import Session


EXAM_SELECT = """
    e.id, e.name, e.academic_year, e.grade_id,
    e.grade_name AS grade, e.section_id, e.section_name AS section,
    e.description,
    e.start_date, e.end_date, e.status, e.created_by,
    e.created_at, e.updated_at
"""

EXAM_SUBJECT_SELECT = """
    es.id, es.exam_id, es.subject_id,
    sub.code AS subject_code, sub.name AS subject_name,
    es.max_marks, es.pass_marks, es.exam_date,
    es.evaluator_staff_id, st.name AS evaluator_name,
    es.evaluation_status, es.created_at, es.updated_at,
    (SELECT COUNT(*) FROM exam_students x
     WHERE x.exam_id = es.exam_id) AS student_count,
    (SELECT COUNT(*) FROM student_marks m
     WHERE m.exam_subject_id = es.id) AS marked_count
"""


def _dict(row):
    return dict(row) if row is not None else None


def _dicts(rows):
    return [dict(row) for row in rows]


def get_grade_class(db: Session, grade_id: int, academic_year: str):
    row = db.execute(
        text("""
            SELECT g.id, g.grade, g.academic_year, g.section_id,
                   sec.section, g.status
            FROM grades g
            JOIN sections sec ON sec.id = g.section_id
            WHERE g.id = :grade_id
              AND LOWER(TRIM(g.academic_year)) = LOWER(TRIM(:academic_year))
              AND LOWER(g.status) = 'active'
        """),
        {"grade_id": grade_id, "academic_year": academic_year},
    ).mappings().first()
    return _dict(row)


def get_active_students_for_class(db: Session, grade: str, section: str):
    rows = db.execute(
        text("""
            SELECT id, name, roll_number
            FROM students
            WHERE LOWER(status) = 'active'
              AND LOWER(TRIM(COALESCE(grade, ''))) = LOWER(TRIM(:grade))
              AND LOWER(TRIM(COALESCE(section, ''))) = LOWER(TRIM(:section))
            ORDER BY roll_number, name, id
        """),
        {"grade": grade, "section": section},
    ).mappings().all()
    return _dicts(rows)


def create_exam(db: Session, payload: dict):
    row = db.execute(
        text(f"""
            INSERT INTO exams (
                name, academic_year, grade_id, grade_name,
                section_id, section_name, description,
                start_date, end_date, status, created_by
            )
            VALUES (
                :name, :academic_year, :grade_id, :grade,
                :section_id, :section, :description,
                :start_date, :end_date, 'draft', :created_by
            )
            RETURNING id
        """),
        payload,
    ).mappings().first()
    return get_exam(db, row["id"]) if row else None


def add_exam_students(db: Session, exam_id: int, student_ids: list[int]):
    if not student_ids:
        return 0
    rows = db.execute(
        text("""
            INSERT INTO exam_students (exam_id, student_id)
            SELECT :exam_id, student_rows.student_id
            FROM unnest(CAST(:student_ids AS INTEGER[]))
                 AS student_rows(student_id)
            ON CONFLICT (exam_id, student_id) DO NOTHING
            RETURNING student_id
        """),
        {"exam_id": exam_id, "student_ids": student_ids},
    ).mappings().all()
    return len(rows)


def get_exam(db: Session, exam_id: int):
    row = db.execute(
        text(f"""
            SELECT {EXAM_SELECT}
            FROM exams e
            WHERE e.id = :exam_id
        """),
        {"exam_id": exam_id},
    ).mappings().first()
    return _dict(row)


def lock_exam(db: Session, exam_id: int):
    row = db.execute(
        text("""
            SELECT id, status, start_date, end_date
            FROM exams
            WHERE id = :exam_id
            FOR UPDATE
        """),
        {"exam_id": exam_id},
    ).mappings().first()
    return _dict(row)


def list_exams(
    db: Session,
    academic_year: str | None,
    grade_id: int | None,
    exam_status: str | None,
    limit: int,
    offset: int,
):
    filters = []
    parameters = {"limit": limit, "offset": offset}

    if academic_year is not None:
        filters.append("e.academic_year = :academic_year")
        parameters["academic_year"] = academic_year
    if grade_id is not None:
        filters.append("e.grade_id = :grade_id")
        parameters["grade_id"] = grade_id
    if exam_status is not None:
        filters.append("e.status = :exam_status")
        parameters["exam_status"] = exam_status

    where_clause = (
        f"WHERE {' AND '.join(filters)}"
        if filters
        else ""
    )

    rows = db.execute(
        text(f"""
            SELECT {EXAM_SELECT}
            FROM exams e
            {where_clause}
            ORDER BY e.start_date DESC, e.id DESC
            LIMIT :limit OFFSET :offset
        """),
        parameters,
    ).mappings().all()
    return _dicts(rows)


def update_exam(db: Session, exam_id: int, payload: dict):
    allowed = {"name", "description", "start_date", "end_date"}
    updates = {key: value for key, value in payload.items() if key in allowed}
    if not updates:
        return get_exam(db, exam_id)
    assignments = ", ".join(f"{field} = :{field}" for field in updates)
    db.execute(
        text(f"""
            UPDATE exams
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE id = :exam_id
        """),
        {**updates, "exam_id": exam_id},
    )
    return get_exam(db, exam_id)


def set_exam_status(db: Session, exam_id: int, exam_status: str):
    db.execute(
        text("""
            UPDATE exams
            SET status = :exam_status, updated_at = CURRENT_TIMESTAMP
            WHERE id = :exam_id
        """),
        {"exam_id": exam_id, "exam_status": exam_status},
    )


def delete_exam(db: Session, exam_id: int):
    row = db.execute(
        text("DELETE FROM exams WHERE id = :exam_id RETURNING id"),
        {"exam_id": exam_id},
    ).mappings().first()
    return _dict(row)


def delete_exam_subject(db: Session, exam_subject_id: int):
    row = db.execute(
        text("""
            DELETE FROM exam_subjects
            WHERE id = :exam_subject_id
            RETURNING id
        """),
        {"exam_subject_id": exam_subject_id},
    ).mappings().first()
    return _dict(row)


def get_subject(db: Session, subject_id: int):
    row = db.execute(
        text("""
            SELECT id, code, name, status
            FROM subjects
            WHERE id = :subject_id
        """),
        {"subject_id": subject_id},
    ).mappings().first()
    return _dict(row)


def get_active_staff(db: Session, staff_id: int):
    row = db.execute(
        text("""
            SELECT st.id, st.name
            FROM staff st
            WHERE st.id = :staff_id
              AND LOWER(st.status) = 'active'
              AND EXISTS (
                  SELECT 1
                  FROM users u
                  JOIN roles r ON r.role_id = u.role_id
                  WHERE u.person_id = st.id
                    AND u.is_active = TRUE
                    AND LOWER(r.role_name) IN ('staff', 'teacher')
              )
        """),
        {"staff_id": staff_id},
    ).mappings().first()
    return _dict(row)


def get_exam_subjects(db: Session, exam_id: int):
    rows = db.execute(
        text(f"""
            SELECT {EXAM_SUBJECT_SELECT}
            FROM exam_subjects es
            JOIN subjects sub ON sub.id = es.subject_id
            JOIN staff st ON st.id = es.evaluator_staff_id
            WHERE es.exam_id = :exam_id
            ORDER BY sub.name, es.id
        """),
        {"exam_id": exam_id},
    ).mappings().all()
    return _dicts(rows)


def get_exam_subject(db: Session, exam_subject_id: int):
    row = db.execute(
        text(f"""
            SELECT {EXAM_SUBJECT_SELECT}, e.status AS exam_status,
                   e.academic_year, e.grade_id
            FROM exam_subjects es
            JOIN exams e ON e.id = es.exam_id
            JOIN subjects sub ON sub.id = es.subject_id
            JOIN staff st ON st.id = es.evaluator_staff_id
            WHERE es.id = :exam_subject_id
        """),
        {"exam_subject_id": exam_subject_id},
    ).mappings().first()
    return _dict(row)


def create_exam_subject(db: Session, exam_id: int, payload: dict):
    row = db.execute(
        text("""
            INSERT INTO exam_subjects (
                exam_id, subject_id, max_marks, pass_marks,
                exam_date, evaluator_staff_id
            )
            VALUES (
                :exam_id, :subject_id, :max_marks, :pass_marks,
                :exam_date, :evaluator_staff_id
            )
            RETURNING id
        """),
        {**payload, "exam_id": exam_id},
    ).mappings().first()
    return get_exam_subject(db, row["id"]) if row else None


def update_exam_subject(db: Session, exam_subject_id: int, payload: dict):
    allowed = {
        "max_marks", "pass_marks", "exam_date", "evaluator_staff_id"
    }
    updates = {key: value for key, value in payload.items() if key in allowed}
    if updates:
        assignments = ", ".join(f"{field} = :{field}" for field in updates)
        db.execute(
            text(f"""
                UPDATE exam_subjects
                SET {assignments}, updated_at = CURRENT_TIMESTAMP
                WHERE id = :exam_subject_id
            """),
            {**updates, "exam_subject_id": exam_subject_id},
        )
    return get_exam_subject(db, exam_subject_id)


def count_exam_subjects(db: Session, exam_id: int) -> int:
    return db.execute(
        text("SELECT COUNT(*) FROM exam_subjects WHERE exam_id = :exam_id"),
        {"exam_id": exam_id},
    ).scalar_one()


def get_exam_subject_progress(db: Session, exam_subject_id: int):
    row = db.execute(
        text("""
            SELECT
                es.id AS exam_subject_id,
                es.exam_id,
                es.evaluation_status,
                (SELECT COUNT(*) FROM exam_students x
                 WHERE x.exam_id = es.exam_id) AS total_students,
                (SELECT COUNT(*) FROM student_marks m
                 WHERE m.exam_subject_id = es.id) AS marked_students
            FROM exam_subjects es
            WHERE es.id = :exam_subject_id
        """),
        {"exam_subject_id": exam_subject_id},
    ).mappings().first()
    if not row:
        return None
    progress = dict(row)
    progress["pending_students"] = (
        progress["total_students"] - progress["marked_students"]
    )
    return progress


def get_assigned_exam_subjects(
    db: Session,
    staff_id: int,
    limit: int,
    offset: int,
):
    rows = db.execute(
        text(f"""
            SELECT {EXAM_SUBJECT_SELECT},
                   e.name AS exam_name, e.academic_year,
                   e.start_date, e.end_date, e.status AS exam_status,
                   e.grade_id, e.grade_name AS grade,
                   e.section_name AS section
            FROM exam_subjects es
            JOIN exams e ON e.id = es.exam_id
            JOIN subjects sub ON sub.id = es.subject_id
            JOIN staff st ON st.id = es.evaluator_staff_id
            WHERE es.evaluator_staff_id = :staff_id
            ORDER BY e.start_date DESC, sub.name
            LIMIT :limit OFFSET :offset
        """),
        {
            "staff_id": staff_id,
            "limit": limit,
            "offset": offset,
        },
    ).mappings().all()
    return _dicts(rows)


def get_assigned_roster(
    db: Session,
    exam_subject_id: int,
    staff_id: int,
    limit: int,
    offset: int,
):
    rows = db.execute(
        text("""
            SELECT
                s.id AS student_id, s.name, s.roll_number,
                m.marks_obtained, m.is_absent, m.remarks,
                m.created_at, m.updated_at
            FROM exam_subjects es
            JOIN exam_students x ON x.exam_id = es.exam_id
            JOIN students s ON s.id = x.student_id
            LEFT JOIN student_marks m
              ON m.exam_subject_id = es.id
             AND m.student_id = s.id
            WHERE es.id = :exam_subject_id
              AND es.evaluator_staff_id = :staff_id
            ORDER BY s.roll_number, s.name, s.id
            LIMIT :limit OFFSET :offset
        """),
        {
            "exam_subject_id": exam_subject_id,
            "staff_id": staff_id,
            "limit": limit,
            "offset": offset,
        },
    ).mappings().all()
    return _dicts(rows)


def get_mark(db: Session, exam_subject_id: int, student_id: int):
    row = db.execute(
        text("""
            SELECT *
            FROM student_marks
            WHERE exam_subject_id = :exam_subject_id
              AND student_id = :student_id
        """),
        {"exam_subject_id": exam_subject_id, "student_id": student_id},
    ).mappings().first()
    return _dict(row)


def get_mark_response(db: Session, exam_subject_id: int, student_id: int):
    row = db.execute(
        text("""
            SELECT
                m.student_id, s.name, s.roll_number,
                m.marks_obtained, m.is_absent, m.remarks,
                m.created_at, m.updated_at
            FROM student_marks m
            JOIN students s ON s.id = m.student_id
            WHERE m.exam_subject_id = :exam_subject_id
              AND m.student_id = :student_id
        """),
        {"exam_subject_id": exam_subject_id, "student_id": student_id},
    ).mappings().first()
    return _dict(row)


def get_exam_student(db: Session, exam_id: int, student_id: int):
    row = db.execute(
        text("""
            SELECT student_id
            FROM exam_students
            WHERE exam_id = :exam_id
              AND student_id = :student_id
        """),
        {"exam_id": exam_id, "student_id": student_id},
    ).first()
    return row is not None


def lock_exam_subject(db: Session, exam_subject_id: int):
    return _dict(db.execute(
        text("""
            SELECT es.id, es.exam_id, es.max_marks,
                   es.evaluation_status, es.evaluator_staff_id,
                   e.status AS exam_status
            FROM exam_subjects es
            JOIN exams e ON e.id = es.exam_id
            WHERE es.id = :exam_subject_id
            FOR UPDATE OF es, e
        """),
        {"exam_subject_id": exam_subject_id},
    ).mappings().first())


def save_mark(
    db: Session,
    exam_subject_id: int,
    student_id: int,
    payload: dict,
    actor_id: int,
    reason: str | None,
    action: str,
):
    previous = get_mark(db, exam_subject_id, student_id)
    if previous is None:
        row = db.execute(
            text("""
                INSERT INTO student_marks (
                    exam_subject_id, student_id, marks_obtained,
                    is_absent, remarks, created_by, updated_by
                )
                VALUES (
                    :exam_subject_id, :student_id, :marks_obtained,
                    :is_absent, :remarks, :actor_id, :actor_id
                )
                RETURNING *
            """),
            {
                **payload,
                "exam_subject_id": exam_subject_id,
                "student_id": student_id,
                "actor_id": actor_id,
            },
        ).mappings().first()
    else:
        row = db.execute(
            text("""
                UPDATE student_marks
                SET marks_obtained = :marks_obtained,
                    is_absent = :is_absent,
                    remarks = :remarks,
                    updated_by = :actor_id,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :mark_id
                RETURNING *
            """),
            {
                **payload,
                "actor_id": actor_id,
                "mark_id": previous["id"],
            },
        ).mappings().first()

    db.execute(
        text("""
            INSERT INTO student_marks_audit (
                student_mark_id, action, previous_marks,
                previous_is_absent, previous_remarks,
                new_marks, new_is_absent, new_remarks,
                reason, changed_by
            )
            VALUES (
                :student_mark_id, :action, :previous_marks,
                :previous_is_absent, :previous_remarks,
                :new_marks, :new_is_absent, :new_remarks,
                :reason, :changed_by
            )
        """),
        {
            "student_mark_id": row["id"],
            "action": action,
            "previous_marks": previous["marks_obtained"] if previous else None,
            "previous_is_absent": previous["is_absent"] if previous else None,
            "previous_remarks": previous["remarks"] if previous else None,
            "new_marks": row["marks_obtained"],
            "new_is_absent": row["is_absent"],
            "new_remarks": row["remarks"],
            "reason": reason,
            "changed_by": actor_id,
        },
    )
    return _dict(row)


def set_evaluation_status(
    db: Session,
    exam_subject_id: int,
    evaluation_status: str,
):
    db.execute(
        text("""
            UPDATE exam_subjects
            SET evaluation_status = :evaluation_status,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :exam_subject_id
        """),
        {
            "exam_subject_id": exam_subject_id,
            "evaluation_status": evaluation_status,
        },
    )


def count_exam_students(db: Session, exam_id: int) -> int:
    return db.execute(
        text("SELECT COUNT(*) FROM exam_students WHERE exam_id = :exam_id"),
        {"exam_id": exam_id},
    ).scalar_one()


def count_subject_marks(db: Session, exam_subject_id: int) -> int:
    return db.execute(
        text("""
            SELECT COUNT(*)
            FROM student_marks
            WHERE exam_subject_id = :exam_subject_id
        """),
        {"exam_subject_id": exam_subject_id},
    ).scalar_one()


def all_subjects_completed(db: Session, exam_id: int) -> bool:
    pending = db.execute(
        text("""
            SELECT COUNT(*)
            FROM exam_subjects
            WHERE exam_id = :exam_id
              AND evaluation_status <> 'completed'
        """),
        {"exam_id": exam_id},
    ).scalar_one()
    return pending == 0


def get_results(
    db: Session,
    exam_id: int,
    student_id: int | None = None,
    staff_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
):
    student_filters = ["x.exam_id = :exam_id"]
    result_filters = ["e.id = :exam_id"]
    parameters = {
        "exam_id": exam_id,
        "limit": limit,
        "offset": offset,
    }

    if student_id is not None:
        student_filters.append("x.student_id = :student_id")
        parameters["student_id"] = student_id
    if staff_id is not None:
        result_filters.append("es.evaluator_staff_id = :staff_id")
        parameters["staff_id"] = staff_id

    rows = db.execute(
        text(f"""
            WITH selected_students AS (
                SELECT x.student_id
                FROM exam_students x
                JOIN students student ON student.id = x.student_id
                WHERE {" AND ".join(student_filters)}
                ORDER BY student.roll_number, student.name, student.id
                LIMIT :limit OFFSET :offset
            )
            SELECT
                e.id AS exam_id, e.name AS exam_name,
                e.academic_year, e.status,
                s.id AS student_id, s.name AS student_name,
                s.roll_number, sub.id AS subject_id,
                sub.name AS subject_name, es.max_marks, es.pass_marks,
                m.marks_obtained, m.is_absent, m.remarks
            FROM exams e
            JOIN selected_students x ON TRUE
            JOIN students s ON s.id = x.student_id
            JOIN exam_subjects es ON es.exam_id = e.id
            JOIN subjects sub ON sub.id = es.subject_id
            LEFT JOIN student_marks m
              ON m.exam_subject_id = es.id
             AND m.student_id = s.id
            WHERE {" AND ".join(result_filters)}
            ORDER BY s.roll_number, sub.name
        """),
        parameters,
    ).mappings().all()
    return _dicts(rows)


def get_exam_ids_for_student(db: Session, student_id: int, exam_id: int):
    row = db.execute(
        text("""
            SELECT e.status
            FROM exams e
            JOIN exam_students x ON x.exam_id = e.id
            WHERE e.id = :exam_id
              AND x.student_id = :student_id
        """),
        {"exam_id": exam_id, "student_id": student_id},
    ).mappings().first()
    return _dict(row)


def has_staff_assignment(db: Session, exam_id: int, staff_id: int) -> bool:
    return db.execute(
        text("""
            SELECT 1
            FROM exam_subjects
            WHERE exam_id = :exam_id
              AND evaluator_staff_id = :staff_id
        """),
        {"exam_id": exam_id, "staff_id": staff_id},
    ).first() is not None


def get_role_name(db: Session, role_id: int):
    row = db.execute(
        text("SELECT role_name FROM roles WHERE role_id = :role_id"),
        {"role_id": role_id},
    ).mappings().first()
    return row["role_name"].strip().lower() if row else None
