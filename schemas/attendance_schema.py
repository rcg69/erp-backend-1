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