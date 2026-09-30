from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db

from schemas.roles_schema import RoleResponse

from security.auth import get_current_user

from services import roles_service


router = APIRouter(
    prefix="/api/roles",
    tags=["Roles"]
)


@router.get("", response_model=list[RoleResponse])
def get_roles(
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return roles_service.get_roles(db)