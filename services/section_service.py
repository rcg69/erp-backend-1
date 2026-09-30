from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from schemas.section_schema import SectionCreate, SectionUpdate


def create_section(
    section_data: SectionCreate,
    db: Session,
):
    try:
        created = db.execute(
            text(
                """
                INSERT INTO sections (section)
                VALUES (:section)
                ON CONFLICT (section) DO NOTHING
                RETURNING id, section
                """
            ),
            {"section": section_data.section},
        ).mappings().first()

        db.commit()

        if not created:
            raise HTTPException(
                status_code=409,
                detail="Section already exists",
            )

        return dict(created)

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Section service unavailable",
        ) from exc


def get_sections(db: Session):
    try:
        rows = db.execute(
            text(
                "SELECT id, section FROM sections ORDER BY section"
            )
        ).mappings().all()

        return [dict(row) for row in rows]

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Section service unavailable",
        ) from exc


def get_section(
    section_id: int,
    db: Session,
):
    row = db.execute(
        text(
            """
            SELECT id, section
            FROM sections
            WHERE id = :section_id
            """
        ),
        {"section_id": section_id},
    ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Section not found",
        )

    return dict(row)


def update_section(
    section_id: int,
    section_data: SectionUpdate,
    db: Session,
):
    payload = {
        "section": section_data.section,
        "section_id": section_id,
    }

    set_clauses = []

    for field_name in ["section"]:
        value = payload[field_name]

        if value is not None:
            set_clauses.append(
                f"{field_name} = :{field_name}"
            )

    if not set_clauses:
        raise HTTPException(
            status_code=400,
            detail="No section fields were provided for update",
        )

    try:
        row = db.execute(
            text(
                f"""
                UPDATE sections
                SET {', '.join(set_clauses)}
                WHERE id = :section_id
                RETURNING id, section
                """
            ),
            payload,
        ).mappings().first()

        db.commit()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Section not found",
            )

        return dict(row)

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Section service unavailable",
        ) from exc


def delete_section(
    section_id: int,
    db: Session,
):
    try:
        row = db.execute(
            text(
                """
                DELETE FROM sections
                WHERE id = :section_id
                RETURNING id, section
                """
            ),
            {"section_id": section_id},
        ).mappings().first()

        db.commit()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Section not found",
            )

        return {
            "success": True,
            "message": "Section deleted successfully",
            "section": dict(row),
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Section service unavailable",
        ) from exc