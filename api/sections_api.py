from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.section_schema import (
    SectionCreate,
    SectionResponse,
    SectionUpdate,
)
from services import section_service


router = APIRouter(
    prefix="/api/sections",
    tags=["Sections"],
)


@router.post(
    "",
    response_model=SectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_section(
    section_data: SectionCreate,
    db: Session = Depends(get_db),
):
    return section_service.create_section(
        section_data,
        db,
    )


@router.get(
    "",
    response_model=list[SectionResponse],
)
def get_sections(
    db: Session = Depends(get_db),
):
    return section_service.get_sections(db)


@router.get(
    "/{section_id}",
    response_model=SectionResponse,
)
def get_section(
    section_id: int,
    db: Session = Depends(get_db),
):
    return section_service.get_section(
        section_id,
        db,
    )


@router.put(
    "/{section_id}",
    response_model=SectionResponse,
)
def update_section(
    section_id: int,
    section_data: SectionUpdate,
    db: Session = Depends(get_db),
):
    return section_service.update_section(
        section_id,
        section_data,
        db,
    )


@router.delete("/{section_id}")
def delete_section(
    section_id: int,
    db: Session = Depends(get_db),
):
    return section_service.delete_section(
        section_id,
        db,
    )