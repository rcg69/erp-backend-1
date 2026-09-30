from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_roles(db: Session):
    try:
        roles = db.execute(
            text(
                "SELECT role_id, role_name "
                "FROM roles "
                "ORDER BY role_id"
            )
        ).mappings().all()

        return [dict(role) for role in roles]

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Role service unavailable"
        ) from exc