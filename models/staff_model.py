
from sqlalchemy import text
from sqlalchemy.orm import Session


STAFF_COLUMNS = "id, name, number, status, created_at"

UPDATABLE_FIELDS = {"name", "number", "status"}


def get_all_staff(db: Session) -> list[dict]:
    rows = db.execute(
        text(
            f"""
            SELECT {STAFF_COLUMNS}
            FROM staff
            ORDER BY id
            """
        )
    ).mappings().all()

    return [dict(row) for row in rows]


def get_staff_by_id(db: Session, staff_id: int) -> dict | None:
    row = db.execute(
        text(
            f"""
            SELECT {STAFF_COLUMNS}
            FROM staff
            WHERE id = :staff_id
            """
        ),
        {"staff_id": staff_id},
    ).mappings().first()

    return dict(row) if row else None


def insert_staff(db: Session, payload: dict) -> dict | None:
    row = db.execute(
        text(
            f"""
            INSERT INTO staff (name, number, status)
            VALUES (:name, :number, :status)
            RETURNING {STAFF_COLUMNS}
            """
        ),
        payload,
    ).mappings().first()

    return dict(row) if row else None


def update_staff_record(
    db: Session,
    staff_id: int,
    payload: dict,
) -> dict | None:
    safe_payload = {
        field: value
        for field, value in payload.items()
        if field in UPDATABLE_FIELDS
    }

    if not safe_payload:
        return None

    assignments = ", ".join(
        f"{field} = :{field}"
        for field in safe_payload
    )

    row = db.execute(
        text(
            f"""
            UPDATE staff
            SET {assignments}
            WHERE id = :staff_id
            RETURNING {STAFF_COLUMNS}
            """
        ),
        {**safe_payload, "staff_id": staff_id},
    ).mappings().first()

    return dict(row) if row else None


def delete_staff_record(db: Session, staff_id: int) -> dict | None:
    row = db.execute(
        text(
            f"""
            DELETE FROM staff
            WHERE id = :staff_id
            RETURNING {STAFF_COLUMNS}
            """
        ),
        {"staff_id": staff_id},
    ).mappings().first()

    return dict(row) if row else None
