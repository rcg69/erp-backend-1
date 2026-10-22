
from sqlalchemy import text
from sqlalchemy.orm import Session


STUDENT_COLUMNS = (
    "id, name, roll_number, admission_date, parent_name, "
    "mobile_number, grade, section, status, created_at"
)

UPDATABLE_FIELDS = {
    "name",
    "roll_number",
    "admission_date",
    "parent_name",
    "mobile_number",
    "grade",
    "section",
    "status",
}

def find_duplicate_roll_number(
    db: Session,
    roll_number: str,
    grade: str | None,
    section: str | None,
    exclude_student_id: int | None = None,
) -> bool:
    query = """
        SELECT 1
        FROM students
        WHERE LOWER(TRIM(roll_number)) = LOWER(TRIM(:roll_number))
          AND LOWER(TRIM(COALESCE(grade, ''))) =
              LOWER(TRIM(COALESCE(:grade, '')))
          AND LOWER(TRIM(COALESCE(section, ''))) =
              LOWER(TRIM(COALESCE(:section, '')))
    """

    params = {
        "roll_number": roll_number,
        "grade": grade,
        "section": section,
    }

    if exclude_student_id is not None:
        query += " AND id <> :exclude_student_id"
        params["exclude_student_id"] = exclude_student_id

    return db.execute(text(query), params).first() is not None
def get_all_students(db: Session) -> list[dict]:
    rows = db.execute(
        text(
            f"""
            SELECT {STUDENT_COLUMNS}
            FROM students
            ORDER BY id
            """
        )
    ).mappings().all()

    return [dict(row) for row in rows]


def get_student_by_id(
    db: Session,
    student_id: int,
) -> dict | None:
    row = db.execute(
        text(
            f"""
            SELECT {STUDENT_COLUMNS}
            FROM students
            WHERE id = :student_id
            LIMIT 1
            """
        ),
        {"student_id": student_id},
    ).mappings().first()

    return dict(row) if row else None


def insert_student(
    db: Session,
    payload: dict,
) -> dict | None:
    row = db.execute(
        text(
            f"""
            INSERT INTO students (
                name,
                roll_number,
                admission_date,
                parent_name,
                mobile_number,
                grade,
                section,
                status
            )
            VALUES (
                :name,
                :roll_number,
                :admission_date,
                :parent_name,
                :mobile_number,
                :grade,
                :section,
                :status
            )
            RETURNING {STUDENT_COLUMNS}
            """
        ),
        payload,
    ).mappings().first()

    return dict(row) if row else None


def update_student_record(
    db: Session,
    student_id: int,
    payload: dict,
) -> dict | None:
    fields = {
        key: value
        for key, value in payload.items()
        if key in UPDATABLE_FIELDS
    }

    if not fields:
        return None

    assignments = ", ".join(
        f"{field} = :{field}"
        for field in fields
    )

    row = db.execute(
        text(
            f"""
            UPDATE students
            SET {assignments}
            WHERE id = :student_id
            RETURNING {STUDENT_COLUMNS}
            """
        ),
        {
            **fields,
            "student_id": student_id,
        },
    ).mappings().first()

    return dict(row) if row else None


def delete_student_record(
    db: Session,
    student_id: int,
) -> dict | None:
    row = db.execute(
        text(
            f"""
            DELETE FROM students
            WHERE id = :student_id
            RETURNING {STUDENT_COLUMNS}
            """
        ),
        {"student_id": student_id},
    ).mappings().first()

    return dict(row) if row else None
