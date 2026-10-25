
from datetime import date, time

from pydantic import BaseModel, Field


ATTENDANCE_STATUSES = r"^(PRESENT|ABSENT|LATE|EXCUSED)$"


class AttendanceCreate(BaseModel):
    session_id: int
    student_id: int
    status: str = Field(pattern=ATTENDANCE_STATUSES)
    remarks: str | None = None


class AttendanceUpdate(BaseModel):
    status: str | None = Field(
        default=None,
        pattern=ATTENDANCE_STATUSES,
    )
    remarks: str | None = None


class AttendanceResponse(BaseModel):
    id: int
    session_id: int
    student_id: int
    academic_year: str | None = None
    status: str
    remarks: str | None = None


class AttendanceBulkItem(BaseModel):
    student_id: int
    status: str = Field(pattern=ATTENDANCE_STATUSES)
    remarks: str | None = None


class AttendanceBulkCreate(BaseModel):
    session_id: int
    records: list[AttendanceBulkItem]


class TeacherAttendanceBulkCreate(BaseModel):
    records: list[AttendanceBulkItem] = Field(min_length=1)


class TeacherClassSession(BaseModel):
    session_id: int
    timetable_id: int
    session_date: date
    grade_id: int | None = None
    section_id: int
    academic_year: str | None = None
    grade: str | None = None
    section: str
    subject_id: int
    subject_name: str
    period_number: int | None = None
    start_time: time
    end_time: time
    room: str | None = None
    is_conducted: bool


class TeacherClassSessionsResponse(BaseModel):
    session_date: date
    classes: list[TeacherClassSession]


class RosterStudent(BaseModel):
    id: int
    name: str | None = None
    roll_number: str | None = None
    attendance_id: int | None = None
    status: str | None = None
    remarks: str | None = None


class ClassRosterResponse(BaseModel):
    grade_id: int
    section_id: int
    grade: str | None = None
    section: str | None = None
    academic_year: str | None = None
    session_date: date
    session_id: int | None = None
    total_students: int
    marked_students: int
    students: list[RosterStudent]


class ReportStudent(BaseModel):
    id: int
    name: str | None = None
    roll_number: str | None = None
    grade: str | None = None
    section: str | None = None


class StudentAttendanceItem(BaseModel):
    attendance_id: int
    session_id: int
    academic_year: str | None = None
    session_date: date
    period_number: int | None = None
    start_time: time
    end_time: time
    subject_id: int
    staff_id: int
    status: str
    remarks: str | None = None


class StudentAttendanceReport(BaseModel):
    academic_year: str
    student: ReportStudent
    total_classes: int
    attended_classes: int
    present: int
    absent: int
    late: int
    excused: int
    percentage: float
    records: list[StudentAttendanceItem]
