from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from schemas.roles_schema import RoleResponse
from security.auth import get_current_user


router = APIRouter(prefix="/api/roles", tags=["Roles"])


@router.get("", response_model=list[RoleResponse])
def get_roles(
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        roles = db.execute(
            text("SELECT role_id, role_name FROM roles ORDER BY role_id")
        ).mappings().all()
        return [dict(role) for role in roles]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Role service unavailable") from exc
