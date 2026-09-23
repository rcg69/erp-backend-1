from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from schemas.staff_schema import StaffCreate, StaffResponse, StaffUpdate
from security.auth import get_current_user, require_admin


router = APIRouter(prefix="/api/staff", tags=["Staff"])

STAFF_COLUMNS = "id, name, number, status, created_at"


def _staff_payload(staff: StaffCreate | StaffUpdate) -> dict:
    return {
        "name": staff.name,
        "number": staff.number,
        "status": staff.status,
    }


@router.post("", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
def create_staff(
    staff: StaffCreate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
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
            raise HTTPException(status_code=502, detail="Staff could not be created")
        return dict(created)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Staff service unavailable") from exc


@router.get("", response_model=list[StaffResponse])
def get_staff(
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text(f"SELECT {STAFF_COLUMNS} FROM staff ORDER BY id")
        ).mappings().all()

        return [dict(row) for row in rows]

    except Exception as exc:
        print("GET STAFF ERROR:", repr(exc))
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@router.get("/{staff_id}", response_model=StaffResponse)
def get_one_staff(
    staff_id: int,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(f"SELECT {STAFF_COLUMNS} FROM staff WHERE id = :staff_id"),
            {"staff_id": staff_id},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Staff not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Staff service unavailable") from exc


@router.put("/{staff_id}", response_model=StaffResponse)
def update_staff(
    staff_id: int,
    staff: StaffUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    payload = _staff_payload(staff)
    update_fields = []

    for field_name in ["name", "number", "status"]:
        value = payload[field_name]
        if value is not None:
            update_fields.append(f"{field_name} = :{field_name}")

    if not update_fields:
        raise HTTPException(status_code=400, detail="No staff fields were provided for update")

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
            {**payload, "staff_id": staff_id},
        ).mappings().first()
        db.commit()
        if not row:
            raise HTTPException(status_code=404, detail="Staff not found")
        return dict(row)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Staff service unavailable") from exc


@router.delete("/{staff_id}")
def delete_staff(
    staff_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            text(f"DELETE FROM staff WHERE id = :staff_id RETURNING {STAFF_COLUMNS}"),
            {"staff_id": staff_id},
        ).mappings().first()
        db.commit()
        if not row:
            raise HTTPException(status_code=404, detail="Staff not found")
        return {"success": True, "message": "Staff deleted successfully", "staff": dict(row)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Staff service unavailable") from exc
