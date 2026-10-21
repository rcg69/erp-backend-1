from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas.class_roster_schema import ClassRosterResponse
from security.auth import require_admin_or_staff
from services import class_roster_service


router = APIRouter(
    prefix="/api/classes",
    tags=["Classes"],
)


@router.get("/students", response_model=ClassRosterResponse)
def get_class_students(
    grade: str = Query(..., min_length=1, max_length=20),
    section: str = Query(..., min_length=1, max_length=20),
    academic_year: str = Query(..., min_length=1, max_length=20),
    current_user=Depends(require_admin_or_staff),
    db: Session = Depends(get_db),
):
    return class_roster_service.get_class_roster(
        grade,
        section,
        academic_year,
        current_user,
        db,
    )
