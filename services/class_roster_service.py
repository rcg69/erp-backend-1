from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_class_roster(
    grade: str,
    section: str,
    academic_year: str,
    current_user: dict,
    db: Session,
) -> dict:
    try:
        class_row = db.execute(
            text(
                """
                SELECT
                    g.id,
                    g.grade,
                    g.academic_year,
                    g.staff_id,
                    sec.id AS section_id,
                    sec.section
                FROM grades g
                JOIN sections sec ON sec.id = g.section_id
                WHERE LOWER(TRIM(g.grade)) = LOWER(TRIM(:grade))
                  AND LOWER(TRIM(sec.section)) = LOWER(TRIM(:section))
                  AND LOWER(TRIM(g.academic_year)) = LOWER(TRIM(:academic_year))
                  AND LOWER(g.status) = 'active'
                LIMIT 1
                """
            ),
            {
                "grade": grade,
                "section": section,
                "academic_year": academic_year,
            },
        ).mappings().first()

        if not class_row:
            raise HTTPException(status_code=404, detail="Active class not found")

        if current_user.get("role") != "admin" and (
            class_row["staff_id"] != current_user.get("person_id")
        ):
            raise HTTPException(
                status_code=403,
                detail="This class is not assigned to the current staff member",
            )

        students = db.execute(
            text(
                """
                SELECT
                    id,
                    (
                        SELECT u.id
                        FROM users u
                        WHERE u.person_id = students.id
                          AND u.role_id = 3
                        ORDER BY u.id
                        LIMIT 1
                    ) AS user_id,
                    name,
                    roll_number,
                    admission_date,
                    parent_name,
                    mobile_number,
                    grade,
                    section,
                    status,
                    created_at
                FROM students
                WHERE LOWER(status) = 'active'
                  AND LOWER(TRIM(grade)) = LOWER(TRIM(:grade))
                  AND LOWER(TRIM(section)) = LOWER(TRIM(:section))
                ORDER BY roll_number, name, id
                """
            ),
            {
                "grade": class_row["grade"],
                "section": class_row["section"],
            },
        ).mappings().all()

        return {
            "academic_year": class_row["academic_year"],
            "grade": class_row["grade"],
            "section": class_row["section"],
            "count": len(students),
            "students": [dict(student) for student in students],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Class roster service unavailable",
        ) from exc
