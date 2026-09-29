from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from schemas.staff_schema import StaffCreate, StaffUpdate


STAFF_COLUMNS = "id, name, number, status, created_at"


def _staff_payload(staff: StaffCreate | StaffUpdate) -> dict:
    return {
        "name": staff.name,
        "number": staff.number,
        "status": staff.status,
    }


def create_staff(
    staff: StaffCreate,
    db: Session,
):
    try:
        created = db.execute(
            text(
                f"""
                INSERT INTO staff (name, number, status)
                VALUES (:name, :number, :status)
                RETURNING {STAFF_COLUMNS}
                """
            ),
            _staff_payload(staff),
        ).mappings().first()

        db.commit()

        if not created:
            raise HTTPException(
                status_code=502,
                detail="Staff could not be created",
            )

        return dict(created)

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff number already exists",
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Staff service unavailable",
        ) from exc


def get_staff(db: Session):
    try:
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

    except Exception as exc:
        print("GET STAFF ERROR:", repr(exc))

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


def get_one_staff(
    staff_id: int,
    db: Session,
):
    try:
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

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Staff not found",
            )

        return dict(row)

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Staff service unavailable",
        ) from exc


def update_staff(
    staff_id: int,
    staff: StaffUpdate,
    db: Session,
):
    payload = _staff_payload(staff)
    update_fields = []

    for field_name in ["name", "number", "status"]:
        value = payload[field_name]

        if value is not None:
            update_fields.append(
                f"{field_name} = :{field_name}"
            )

    if not update_fields:
        raise HTTPException(
            status_code=400,
            detail="No staff fields were provided for update",
        )

    try:
        row = db.execute(
            text(
                f"""
                UPDATE staff
                SET {', '.join(update_fields)}
                WHERE id = :staff_id
                RETURNING {STAFF_COLUMNS}
                """
            ),
            {
                **payload,
                "staff_id": staff_id,
            },
        ).mappings().first()

        db.commit()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Staff not found",
            )

        return dict(row)

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff number already exists",
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail="Staff service unavailable",
        ) from exc


def delete_staff(
    staff_id: int,
    db: Session,
):
    try:
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

        db.commit()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Staff not found",
            )

        return {
            "success": True,
            "message": "Staff deleted successfully",
            "staff": dict(row),
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail="Staff service unavailable",
        ) from exc