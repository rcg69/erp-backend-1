
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.attendance_schema import (
    AttendanceBulkCreate,
    AttendanceCreate,
    AttendanceResponse,
    AttendanceUpdate,
    ClassRosterResponse,
    StudentAttendanceReport,
    TeacherAttendanceBulkCreate,
    TeacherClassSessionsResponse,
)
from security.auth import require_admin, require_staff
from services import attendance_service


router = APIRouter(
    prefix="/api/attendance",
    tags=["Attendance"],
)


@router.post(
    "",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_attendance(
    data: AttendanceCreate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return attendance_service.create_attendance(data, db)


@router.get(
    "",
    response_model=list[AttendanceResponse],
)
def get_attendance(db: Session = Depends(get_db)):
    return attendance_service.get_attendance(db)


@router.get(
    "/roster",
    response_model=ClassRosterResponse,
)
def get_class_roster(
    grade_id: int = Query(...),
    section_id: int = Query(...),
    session_date: date = Query(...),
    session_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return attendance_service.get_class_roster(
        grade_id, section_id, session_date, session_id, db
    )


@router.get(
    "/student-report",
    response_model=StudentAttendanceReport,
)
def get_student_attendance_report(
    roll_number: str = Query(...),
    grade_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return attendance_service.get_student_attendance_report(
        roll_number, grade_id, section_id, db
    )


@router.get(
    "/teacher/classes",
    response_model=TeacherClassSessionsResponse,
)
def get_teacher_class_sessions(
    session_date: date | None = Query(default=None),
    current_user=Depends(require_staff),
    db: Session = Depends(get_db),
):
    return attendance_service.get_teacher_class_sessions(
        session_date or date.today(),
        current_user["person_id"],
        db,
    )


@router.get(
    "/teacher/sessions/{session_id}/roster",
    response_model=ClassRosterResponse,
)
def get_teacher_class_roster(
    session_id: int,
    current_user=Depends(require_staff),
    db: Session = Depends(get_db),
):
    return attendance_service.get_teacher_class_roster(
        session_id, current_user["person_id"], db
    )


@router.put("/teacher/sessions/{session_id}/attendance")
def save_teacher_class_attendance(
    session_id: int,
    data: TeacherAttendanceBulkCreate,
    current_user=Depends(require_staff),
    db: Session = Depends(get_db),
):
    return attendance_service.save_teacher_class_attendance(
        session_id, current_user["person_id"], data, db
    )


@router.post(
    "/bulk",
    status_code=status.HTTP_201_CREATED,
)
def create_bulk_attendance(
    data: AttendanceBulkCreate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return attendance_service.create_bulk_attendance(data, db)


@router.get(
    "/{attendance_id}",
    response_model=AttendanceResponse,
)
def get_attendance_record(
    attendance_id: int,
    db: Session = Depends(get_db),
):
    return attendance_service.get_one_attendance(attendance_id, db)


@router.put(
    "/{attendance_id}",
    response_model=AttendanceResponse,
)
def update_attendance(
    attendance_id: int,
    data: AttendanceUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return attendance_service.update_attendance(
        attendance_id, data, db
    )


@router.delete("/{attendance_id}")
def delete_attendance(
    attendance_id: int,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return attendance_service.delete_attendance(attendance_id, db)
