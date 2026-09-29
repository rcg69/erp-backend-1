from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db

from schemas.timetable_schema import (
    TimetableAssignment,
    TimetableCreate,
    TimetableOpenRequest,
    TimetableResponse,
    TimetableUpdate,
)

from schemas.class_session_schema import (
    ClassDaySessionsResponse,
    ClassSessionCreate,
    ClassSessionResponse,
    ClassSessionUpdate,
    SessionGenerateRequest,
    SessionGenerateResponse,
)

from services import scheduling_service


router = APIRouter(
    prefix="/api/scheduling",
    tags=["Scheduling"],
)


# =========================================================
# TIMETABLES
# =========================================================

@router.post(
    "/timetables/open",
    response_model=list[TimetableResponse],
)
def open_timetable(
    open_data: TimetableOpenRequest,
    db: Session = Depends(get_db),
):
    return scheduling_service.open_timetable(
        open_data,
        db,
    )


@router.put(
    "/timetables/{timetable_id}/assignment",
    response_model=TimetableResponse,
)
def assign_timetable_slot(
    timetable_id: int,
    assignment: TimetableAssignment,
    db: Session = Depends(get_db),
):
    return scheduling_service.assign_timetable_slot(
        timetable_id,
        assignment,
        db,
    )


@router.post(
    "/timetables",
    response_model=TimetableResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_timetable(
    timetable_data: TimetableCreate,
    db: Session = Depends(get_db),
):
    return scheduling_service.create_timetable(
        timetable_data,
        db,
    )


@router.get(
    "/timetables",
    response_model=list[TimetableResponse],
)
def get_timetables(
    grade_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return scheduling_service.get_timetables(
        grade_id,
        section_id,
        db,
    )


@router.get(
    "/timetables/{timetable_id}",
    response_model=TimetableResponse,
)
def get_timetable(
    timetable_id: int,
    db: Session = Depends(get_db),
):
    return scheduling_service.get_timetable(
        timetable_id,
        db,
    )


@router.put(
    "/timetables/{timetable_id}",
    response_model=TimetableResponse,
)
def update_timetable(
    timetable_id: int,
    timetable_data: TimetableUpdate,
    db: Session = Depends(get_db),
):
    return scheduling_service.update_timetable(
        timetable_id,
        timetable_data,
        db,
    )


@router.delete(
    "/timetables/{timetable_id}",
)
def delete_timetable(
    timetable_id: int,
    db: Session = Depends(get_db),
):
    return scheduling_service.delete_timetable(
        timetable_id,
        db,
    )


# =========================================================
# CLASS SESSIONS
# =========================================================

@router.post(
    "/sessions/generate",
    response_model=SessionGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_class_sessions(
    generate_data: SessionGenerateRequest,
    db: Session = Depends(get_db),
):
    return scheduling_service.generate_class_sessions(
        generate_data,
        db,
    )


@router.post(
    "/sessions",
    response_model=ClassSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_class_session(
    session_data: ClassSessionCreate,
    db: Session = Depends(get_db),
):
    return scheduling_service.create_class_session(
        session_data,
        db,
    )


@router.get(
    "/sessions",
    response_model=list[ClassSessionResponse],
)
def get_class_sessions(
    db: Session = Depends(get_db),
):
    return scheduling_service.get_class_sessions(
        db,
    )


@router.get(
    "/sessions/by-class",
    response_model=ClassDaySessionsResponse,
)
def get_sessions_for_class_on_date(
    grade_id: int = Query(...),
    section_id: int = Query(...),
    session_date: date = Query(...),
    db: Session = Depends(get_db),
):
    return scheduling_service.get_sessions_for_class_on_date(
        grade_id,
        section_id,
        session_date,
        db,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=ClassSessionResponse,
)
def get_class_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    return scheduling_service.get_class_session(
        session_id,
        db,
    )


@router.put(
    "/sessions/{session_id}",
    response_model=ClassSessionResponse,
)
def update_class_session(
    session_id: int,
    session_data: ClassSessionUpdate,
    db: Session = Depends(get_db),
):
    return scheduling_service.update_class_session(
        session_id,
        session_data,
        db,
    )


@router.delete(
    "/sessions/{session_id}",
)
def delete_class_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    return scheduling_service.delete_class_session(
        session_id,
        db,
    )