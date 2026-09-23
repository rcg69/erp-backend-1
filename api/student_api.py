from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from schemas.student_schema import StudentCreate, StudentUpdate
from security.auth import get_current_user, require_admin


router = APIRouter(prefix="/api/students", tags=["Students/Staff"])


STUDENT_COLUMNS = "id, name, roll_number, admission_date, parent_name, mobile_number, grade, section, status, created_at"


def _student_payload(student: StudentCreate | StudentUpdate) -> dict:
    return {
        "name": student.name,
        "roll_number": student.roll_number,
        "admission_date": student.admission_date,
        "parent_name": student.parent_name,
        "mobile_number": student.mobile_number,
        "grade": student.grade,
        "section": student.section,
        "status": getattr(student, "status", None),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_student(
    student: StudentCreate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        created = db.execute(
            text(
                f"""
                INSERT INTO students (name, roll_number, admission_date, parent_name, mobile_number, grade, section, status)
                VALUES (:name, :roll_number, :admission_date, :parent_name, :mobile_number, :grade, :section, :status)
                RETURNING {STUDENT_COLUMNS}
                """
            ),
            _student_payload(student),
        ).mappings().first()
        db.commit()
        if not created:
            raise HTTPException(status_code=502, detail="Student could not be created")
        return {"success": True, "message": "Student created successfully", "student": dict(created)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Student service unavailable") from exc


@router.get("")
def get_students(
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        students = db.execute(
            text(f"SELECT {STUDENT_COLUMNS} FROM students ORDER BY id")
        ).mappings().all()
        students = [dict(student) for student in students]
        return {"success": True, "count": len(students), "students": students}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Student service unavailable") from exc


@router.get("/{student_id}")
def get_student(
    student_id: int,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        student = db.execute(
            text(f"SELECT {STUDENT_COLUMNS} FROM students WHERE id = :student_id"),
            {"student_id": student_id},
        ).mappings().first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return {"success": True, "student": dict(student)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Student service unavailable") from exc


@router.put("/{student_id}")
def update_student(
    student_id: int,
    student: StudentUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    payload = _student_payload(student)
    update_fields = []

    for field_name in ["name", "roll_number", "admission_date", "parent_name", "mobile_number", "grade", "section", "status"]:
        value = payload[field_name]
        if value is not None:
            update_fields.append(f"{field_name} = :{field_name}")

    if not update_fields:
        raise HTTPException(status_code=400, detail="No student fields were provided for update")

    try:
        updated = db.execute(
            text(
                f"""
                UPDATE students
                SET {', '.join(update_fields)}
                WHERE id = :student_id
                RETURNING {STUDENT_COLUMNS}
                """
            ),
            {**payload, "student_id": student_id},
        ).mappings().first()
        db.commit()
        if not updated:
            raise HTTPException(status_code=404, detail="Student not found")
        return {"success": True, "message": "Student updated successfully", "student": dict(updated)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Student service unavailable") from exc


@router.delete("/{student_id}")
def delete_student(
    student_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        deleted = db.execute(
            text(f"DELETE FROM students WHERE id = :student_id RETURNING {STUDENT_COLUMNS}"),
            {"student_id": student_id},
        ).mappings().first()
        db.commit()
        if not deleted:
            raise HTTPException(status_code=404, detail="Student not found")
        return {"success": True, "message": "Student deleted successfully", "student": dict(deleted)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Student service unavailable") from exc
