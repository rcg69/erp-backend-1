from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from schemas.grade_schema import GradeCreate, GradeResponse, GradeUpdate

router = APIRouter(prefix="/api/grades", tags=["Grades"])


@router.post("", response_model=GradeResponse, status_code=status.HTTP_201_CREATED)
def create_grade(grade_data: GradeCreate, db: Session = Depends(get_db)):
    try:
        record = db.execute(
            text(
                """
                INSERT INTO grades (academic_year, grade, section_id, staff_id, status)
                VALUES (:academic_year, :grade, :section_id, :staff_id, :status)
                ON CONFLICT (academic_year, grade) DO NOTHING
                RETURNING id, academic_year, grade, section_id, staff_id, status
                """
            ),
            {
                "academic_year": grade_data.academic_year,
                "grade": grade_data.grade,
                "section_id": grade_data.section_id,
                "staff_id": grade_data.staff_id,
                "status": grade_data.status or "active",
            },
        ).mappings().first()
        db.commit()

        if not record:
            raise HTTPException(status_code=409, detail="Grade already exists for this academic year")

        return dict(record)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Grade service unavailable") from exc


@router.get("", response_model=list[GradeResponse])
def get_grades(db: Session = Depends(get_db)):
    try:
        rows = db.execute(
            text("SELECT id, academic_year, grade, section_id, staff_id, status FROM grades ORDER BY academic_year, grade")
        ).mappings().all()
        return [dict(row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Grade service unavailable") from exc


@router.get("/{grade_id}", response_model=GradeResponse)
def get_grade(grade_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT id, academic_year, grade, section_id, staff_id, status FROM grades WHERE id = :grade_id"),
        {"grade_id": grade_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Grade not found")

    return dict(row)


@router.put("/{grade_id}", response_model=GradeResponse)
def update_grade(grade_id: int, grade_data: GradeUpdate, db: Session = Depends(get_db)):
    payload = {
        "academic_year": grade_data.academic_year,
        "grade": grade_data.grade,
        "section_id": grade_data.section_id,
        "staff_id": grade_data.staff_id,
        "status": grade_data.status,
        "grade_id": grade_id,
    }

    set_clauses = []
    for field_name in ["academic_year", "grade", "section_id", "staff_id", "status"]:
        value = payload[field_name]
        if value is not None:
            set_clauses.append(f"{field_name} = :{field_name}")

    if not set_clauses:
        raise HTTPException(status_code=400, detail="No grade fields were provided for update")

    try:
        row = db.execute(
            text(
                f"""
                UPDATE grades
                SET {', '.join(set_clauses)}
                WHERE id = :grade_id
                RETURNING id, academic_year, grade, section_id, staff_id, status
                """
            ),
            payload,
        ).mappings().first()
        db.commit()

        if not row:
            raise HTTPException(status_code=404, detail="Grade not found")

        return dict(row)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Grade service unavailable") from exc


@router.delete("/{grade_id}")
def delete_grade(grade_id: int, db: Session = Depends(get_db)):
    try:
        row = db.execute(
            text("DELETE FROM grades WHERE id = :grade_id RETURNING id, academic_year, grade, section_id, staff_id, status"),
            {"grade_id": grade_id},
        ).mappings().first()
        db.commit()

        if not row:
            raise HTTPException(status_code=404, detail="Grade not found")

        return {"success": True, "message": "Grade deleted successfully", "grade": dict(row)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Grade service unavailable") from exc
