from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from schemas.section_schema import SectionCreate, SectionResponse, SectionUpdate

router = APIRouter(prefix="/api/sections", tags=["Sections"])


@router.post("", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
def create_section(section_data: SectionCreate, db: Session = Depends(get_db)):
    try:
        created = db.execute(
            text(
                """
                INSERT INTO sections (section, staff_id)
                VALUES (:section, :staff_id)
                ON CONFLICT (section) DO NOTHING
                RETURNING id, section, staff_id
                """
            ),
            {"section": section_data.section, "staff_id": section_data.staff_id},
        ).mappings().first()
        db.commit()

        if not created:
            raise HTTPException(status_code=409, detail="Section already exists")

        return dict(created)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Section service unavailable") from exc


@router.get("", response_model=list[SectionResponse])
def get_sections(db: Session = Depends(get_db)):
    try:
        rows = db.execute(
            text("SELECT id, section, staff_id FROM sections ORDER BY section")
        ).mappings().all()
        return [dict(row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Section service unavailable") from exc


@router.get("/{section_id}", response_model=SectionResponse)
def get_section(section_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT id, section, staff_id FROM sections WHERE id = :section_id"),
        {"section_id": section_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Section not found")

    return dict(row)


@router.put("/{section_id}", response_model=SectionResponse)
def update_section(section_id: int, section_data: SectionUpdate, db: Session = Depends(get_db)):
    payload = {"section": section_data.section, "staff_id": section_data.staff_id, "section_id": section_id}
    set_clauses = []

    for field_name in ["section", "staff_id"]:
        value = payload[field_name]
        if value is not None:
            set_clauses.append(f"{field_name} = :{field_name}")

    if not set_clauses:
        raise HTTPException(status_code=400, detail="No section fields were provided for update")

    try:
        row = db.execute(
            text(
                f"""
                UPDATE sections
                SET {', '.join(set_clauses)}
                WHERE id = :section_id
                RETURNING id, section, staff_id
                """
            ),
            payload,
        ).mappings().first()
        db.commit()

        if not row:
            raise HTTPException(status_code=404, detail="Section not found")

        return dict(row)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Section service unavailable") from exc


@router.delete("/{section_id}")
def delete_section(section_id: int, db: Session = Depends(get_db)):
    try:
        row = db.execute(
            text("DELETE FROM sections WHERE id = :section_id RETURNING id, section, staff_id"),
            {"section_id": section_id},
        ).mappings().first()
        db.commit()

        if not row:
            raise HTTPException(status_code=404, detail="Section not found")

        return {"success": True, "message": "Section deleted successfully", "section": dict(row)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Section service unavailable") from exc