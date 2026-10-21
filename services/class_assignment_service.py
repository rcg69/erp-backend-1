import re

from sqlalchemy import text
from sqlalchemy.orm import Session


def _normalize_grade(value) -> str | None:
    if value is None:
        return None

    grade = str(value).strip().lower()
    if not grade:
        return None

    match = re.search(r"\d+", grade)
    return match.group(0) if match else grade


def teacher_assigned_to_student_class(
    db: Session,
    staff_id: int,
    student_grade,
    student_section,
) -> bool:
    if student_grade is None or student_section is None:
        return False

    assignments = db.execute(
        text(
            """
            SELECT g.grade, sec.section
            FROM grades g
            JOIN sections sec ON sec.id = g.section_id
            WHERE g.staff_id = :staff_id
              AND LOWER(g.status) = 'active'
            """
        ),
        {"staff_id": staff_id},
    ).mappings().all()

    normalized_grade = _normalize_grade(student_grade)
    normalized_section = str(student_section).strip().lower()
    return any(
        _normalize_grade(assignment["grade"]) == normalized_grade
        and str(assignment["section"]).strip().lower() == normalized_section
        for assignment in assignments
    )
