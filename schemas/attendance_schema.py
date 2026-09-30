from datetime import date, time

from pydantic import BaseModel, Field


class AttendanceCreate(BaseModel):
    session_id: int
    student_id: int
    status: str = Field(
        pattern="^(PRESENT|ABSENT|LATE|EXCUSED)$"
    )
    remarks: str | None = None


class AttendanceUpdate(BaseModel):
    status: str | None = Field(
        default=None,
        pattern="^(PRESENT|ABSENT|LATE|EXCUSED)$"
    )
    remarks: str | None = None


class AttendanceResponse(BaseModel):
    id: int
    session_id: int
    student_id: int
    status: str
    remarks: str | None
class AttendanceBulkItem(BaseModel):
    student_id: int
    status: str = Field(
        pattern="^(PRESENT|ABSENT|LATE|EXCUSED)$"
    )
    remarks: str | None = None


class AttendanceBulkCreate(BaseModel):
    session_id: int
    records: list[AttendanceBulkItem]


class RosterStudent(BaseModel):
    id: int
    name: str | None = None
    roll_number: str | None = None

    # Filled only when a session_id is supplied and attendance exists.
    attendance_id: int | None = None
    status: str | None = None
    remarks: str | None = None


class ClassRosterResponse(BaseModel):
    grade_id: int
    section_id: int
    grade: str | None = None
    section: str | None = None
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
    session_date: date
    period_number: int | None = None
    start_time: time
    end_time: time
    subject_id: int
    staff_id: int
    status: str
    remarks: str | None = None


class StudentAttendanceReport(BaseModel):
    student: ReportStudent

    # Classes counted = every class session with an attendance record.
    # Attended = PRESENT + LATE.
    total_classes: int
    attended_classes: int
    present: int
    absent: int
    late: int
    excused: int
    percentage: float

    records: list[StudentAttendanceItem]